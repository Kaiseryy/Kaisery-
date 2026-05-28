import os
import json
import httpx

from agent.tools_and_schemas import SearchQueryList, Reflection
from dotenv import load_dotenv
from langchain_core.messages import AIMessage
from langgraph.types import Send
from langgraph.graph import StateGraph
from langgraph.graph import START, END
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from ddgs import DDGS

from agent.state import (
    OverallState,
    QueryGenerationState,
    ReflectionState,
    WebSearchState,
)
from agent.configuration import Configuration
from agent.prompts import (
    get_current_date,
    query_writer_instructions,
    web_searcher_instructions,
    reflection_instructions,
    answer_instructions,
)
from agent.utils import (
    format_search_results,
    get_research_topic,
)

load_dotenv()

if os.getenv("DEEPSEEK_API_KEY") is None:
    raise ValueError("DEEPSEEK_API_KEY is not set")

DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"


def _create_llm(model: str, temperature: float = 1.0) -> ChatOpenAI:
    # Create httpx client without proxy to avoid interference from system proxy
    http_client = httpx.Client(proxy=None)
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        max_retries=2,
        base_url=DEEPSEEK_BASE_URL,
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        http_client=http_client,
    )


def _parse_json_response(text: str) -> dict:
    """Extract JSON from LLM response text, handling markdown code blocks."""
    if not text or not text.strip():
        raise ValueError("LLM returned empty response")
    text = text.strip()
    if text.startswith("```"):
        # Remove markdown code block
        lines = text.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        text = "\n".join(lines)
    return json.loads(text)


# Nodes
def generate_query(state: OverallState, config: RunnableConfig) -> QueryGenerationState:
    """LangGraph node that generates search queries based on the User's question."""
    configurable = Configuration.from_runnable_config(config)

    if state.get("initial_search_query_count") is None:
        state["initial_search_query_count"] = configurable.number_of_initial_queries

    llm = _create_llm(configurable.query_generator_model, temperature=1.0)

    current_date = get_current_date()
    formatted_prompt = query_writer_instructions.format(
        current_date=current_date,
        research_topic=get_research_topic(state["messages"]),
        number_queries=state["initial_search_query_count"],
    )
    result = llm.invoke(formatted_prompt)
    parsed = _parse_json_response(result.content)
    return {"search_query": parsed["query"]}


def continue_to_web_research(state: QueryGenerationState):
    """LangGraph node that sends the search queries to the web research node."""
    return [
        Send("web_research", {"search_query": search_query, "id": int(idx)})
        for idx, search_query in enumerate(state["search_query"])
    ]


def web_research(state: WebSearchState, config: RunnableConfig) -> OverallState:
    """LangGraph node that performs web research using DuckDuckGo search."""
    configurable = Configuration.from_runnable_config(config)
    formatted_prompt = web_searcher_instructions.format(
        current_date=get_current_date(),
        research_topic=state["search_query"],
    )

    # Perform DuckDuckGo search
    search_results = []
    with DDGS() as ddgs:
        for r in ddgs.text(state["search_query"], max_results=5):
            search_results.append({
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", ""),
            })

    # Format search results with numbered sources for inline citation
    search_context = format_search_results(search_results)

    # Instruct LLM to cite sources by number
    citation_prompt = (
        f"{formatted_prompt}\n\n"
        f"Search Results:\n{search_context}\n\n"
        "IMPORTANT: When using information from a search result, cite it inline "
        "using the source number in brackets, e.g. [0], [1], [2]. "
        "This is required for proper attribution."
    )

    # Use LLM to synthesize search results
    llm = _create_llm(configurable.query_generator_model, temperature=0)
    result = llm.invoke(citation_prompt)

    # Build sources mapping for URL replacement
    sources_gathered = [
        {
            "short_url": f"[{idx}]",
            "value": r["url"],
            "title": r["title"],
        }
        for idx, r in enumerate(search_results)
    ]

    return {
        "sources_gathered": sources_gathered,
        "search_query": [state["search_query"]],
        "web_research_result": [result.content],
    }


def reflection(state: OverallState, config: RunnableConfig) -> ReflectionState:
    """LangGraph node that identifies knowledge gaps and generates follow-up queries."""
    configurable = Configuration.from_runnable_config(config)
    state["research_loop_count"] = state.get("research_loop_count", 0) + 1
    reasoning_model = state.get("reasoning_model", configurable.reflection_model)

    current_date = get_current_date()
    formatted_prompt = reflection_instructions.format(
        current_date=current_date,
        research_topic=get_research_topic(state["messages"]),
        summaries="\n\n---\n\n".join(state["web_research_result"]),
    )
    llm = _create_llm(reasoning_model, temperature=1.0)
    result = llm.invoke(formatted_prompt)
    parsed = _parse_json_response(result.content)

    return {
        "is_sufficient": parsed["is_sufficient"],
        "knowledge_gap": parsed["knowledge_gap"],
        "follow_up_queries": parsed["follow_up_queries"],
        "research_loop_count": state["research_loop_count"],
        "number_of_ran_queries": len(state["search_query"]),
    }


def evaluate_research(
    state: ReflectionState,
    config: RunnableConfig,
) -> OverallState:
    """LangGraph routing function that determines the next step in the research flow."""
    configurable = Configuration.from_runnable_config(config)
    max_research_loops = (
        state.get("max_research_loops")
        if state.get("max_research_loops") is not None
        else configurable.max_research_loops
    )
    if state["is_sufficient"] or state["research_loop_count"] >= max_research_loops:
        return "finalize_answer"
    else:
        return [
            Send(
                "web_research",
                {
                    "search_query": follow_up_query,
                    "id": state["number_of_ran_queries"] + int(idx),
                },
            )
            for idx, follow_up_query in enumerate(state["follow_up_queries"])
        ]


def finalize_answer(state: OverallState, config: RunnableConfig):
    """LangGraph node that finalizes the research summary."""
    configurable = Configuration.from_runnable_config(config)
    reasoning_model = state.get("reasoning_model") or configurable.answer_model

    current_date = get_current_date()
    formatted_prompt = answer_instructions.format(
        current_date=current_date,
        research_topic=get_research_topic(state["messages"]),
        summaries="\n---\n\n".join(state["web_research_result"]),
    )

    llm = _create_llm(reasoning_model, temperature=0)
    result = llm.invoke(formatted_prompt)

    # Replace inline citation markers [0], [1], etc. with clickable links
    content = result.content
    for source in state["sources_gathered"]:
        marker = source["short_url"]  # e.g. "[0]"
        link = f"[{marker[1:-1]}]({source['value']})"
        content = content.replace(marker, link)

    # Build a set of all unique sources
    seen_urls = set()
    unique_sources = []
    for source in state["sources_gathered"]:
        if source["value"] not in seen_urls:
            seen_urls.add(source["value"])
            unique_sources.append(source)

    return {
        "messages": [AIMessage(content=content)],
        "sources_gathered": unique_sources,
    }


# Create our Agent Graph
builder = StateGraph(OverallState, config_schema=Configuration)

builder.add_node("generate_query", generate_query)
builder.add_node("web_research", web_research)
builder.add_node("reflection", reflection)
builder.add_node("finalize_answer", finalize_answer)

builder.add_edge(START, "generate_query")
builder.add_conditional_edges(
    "generate_query", continue_to_web_research, ["web_research"]
)
builder.add_edge("web_research", "reflection")
builder.add_conditional_edges(
    "reflection", evaluate_research, ["web_research", "finalize_answer"]
)
builder.add_edge("finalize_answer", END)

graph = builder.compile(name="pro-search-agent")

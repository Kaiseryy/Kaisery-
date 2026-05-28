from typing import Any, Dict, List
from langchain_core.messages import AnyMessage, AIMessage, HumanMessage


def get_research_topic(messages: List[AnyMessage]) -> str:
    """
    Get the research topic from the messages.
    """
    if len(messages) == 1:
        research_topic = messages[-1].content
    else:
        research_topic = ""
        for message in messages:
            if isinstance(message, HumanMessage):
                research_topic += f"User: {message.content}\n"
            elif isinstance(message, AIMessage):
                research_topic += f"Assistant: {message.content}\n"
    return research_topic


def format_search_results(results: List[Dict[str, str]]) -> str:
    """Format DuckDuckGo search results into a context string for the LLM."""
    if not results:
        return "No search results found."
    formatted = []
    for idx, r in enumerate(results):
        formatted.append(
            f"[{idx}] {r['title']}\nURL: {r['url']}\nSnippet: {r['snippet']}"
        )
    return "\n\n".join(formatted)

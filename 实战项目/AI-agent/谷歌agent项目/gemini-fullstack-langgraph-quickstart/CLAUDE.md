# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A deep research agent that uses LangGraph to orchestrate an iterative search-and-synthesize loop. The agent generates search queries, performs web research via DuckDuckGo, reflects on knowledge gaps, and produces cited answers. Originally built on Google Gemini, now uses DeepSeek V4 API (OpenAI-compatible).

## Commands

```bash
# Backend
cd backend
pip install -e .                    # Install in editable mode
langgraph dev --port 8123           # Start backend (dev mode with hot reload)
python examples/cli_research.py "question"  # CLI quick test

# Frontend
cd frontend
npm install                         # Install dependencies
npm run dev                         # Start Vite dev server (http://localhost:5173/app/)

# Both together
make dev                            # Starts frontend + backend concurrently
```

## Architecture

### Agent Graph (`backend/src/agent/graph.py`)

The core is a LangGraph `StateGraph` with 4 nodes:

```
generate_query → web_research → reflection → (loop or finalize_answer)
```

- **generate_query**: LLM generates search queries (returns JSON with `query` list)
- **web_research**: DuckDuckGo search + LLM synthesizes results with inline citations `[0]`, `[1]`
- **reflection**: LLM evaluates if knowledge is sufficient; generates follow-up queries if not
- **finalize_answer**: LLM produces final answer; `[N]` markers are replaced with clickable source URLs

### Key Design Decisions

- **No structured output**: DeepSeek API doesn't support `response_format`. Instead, prompts request JSON and `_parse_json_response()` extracts it manually.
- **Proxy bypass**: `_create_llm()` creates `httpx.Client(proxy=None)` to avoid system proxy (`HTTP_PROXY`) interfering with DeepSeek API calls.
- **Inline citations**: `web_research` numbers sources `[0]`–`[4]` and prompts LLM to cite them. `finalize_answer` replaces markers with markdown links.

### Files to Know

| File | Purpose |
|------|---------|
| `backend/src/agent/graph.py` | Agent graph definition, all node functions, LLM client setup |
| `backend/src/agent/configuration.py` | Model names, query count, max loops config |
| `backend/src/agent/prompts.py` | All LLM prompts (query gen, search, reflection, answer) |
| `backend/src/agent/utils.py` | `get_research_topic()`, `format_search_results()` |
| `backend/src/agent/state.py` | TypedDict state definitions for graph |
| `backend/src/agent/tools_and_schemas.py` | Pydantic models (SearchQueryList, Reflection) |
| `frontend/src/App.tsx` | Main React component, `useStream` hook connects to backend |
| `frontend/vite.config.ts` | Proxy `/api` to backend port 8123 |

### Environment

`backend/.env` requires:
```
DEEPSEEK_API_KEY=sk-...
```

### API Details

- DeepSeek base URL: `https://api.deepseek.com/v1`
- Models: `deepseek-v4-flash` (fast/cheap), `deepseek-v4-pro` (reasoning)
- Frontend connects to `http://localhost:8123` (LangGraph dev server)
- Assistant ID in `frontend/src/App.tsx` must match the UUID from `langgraph dev` output

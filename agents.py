import functools
import operator
import os
import time
import uuid
from typing import Annotated, Any, TypedDict

from dotenv import load_dotenv, find_dotenv
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langgraph.graph import END, StateGraph
from zep_cloud import Zep, Message
from zep_cloud.errors import NotFoundError

# ---------------------------
# 1. LOAD & VALIDATE ENV
# ---------------------------
dotenv_path = find_dotenv()
if not dotenv_path:
    raise FileNotFoundError(
        "No .env file found. Create one in the same folder with:\n"
        "GROQ_API_KEY=gsk_...\nZEP_API_KEY=your_zep_key\nTAVILY_API_KEY=your_tavily_key"
    )
load_dotenv(dotenv_path, override=True)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ZEP_API_KEY = os.getenv("ZEP_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

for key, name in [(GROQ_API_KEY, "GROQ_API_KEY"), (ZEP_API_KEY, "ZEP_API_KEY"), (TAVILY_API_KEY, "TAVILY_API_KEY")]:
    if not key:
        raise ValueError(f"{name} not found in .env file. Please add it.")

print("✅ Loaded backend API keys from .env.")

# ---------------------------
# 2. STATE & UTILITIES
# ---------------------------
class ResearchState(TypedDict):
    topic: str
    search_results: Annotated[list[dict[str, str]], operator.add]
    summaries: Annotated[list[str], operator.add]
    final_report: str
    source_count: int
    report_length: str
    tone: str
    include_citations: bool
    user_id: str
    thread_id: str
    zep_context: str

def get_zep_client() -> Zep:
    return Zep(api_key=ZEP_API_KEY)

def ensure_zep_user_and_thread(user_id: str, thread_id: str) -> None:
    zep = get_zep_client()
    try:
        zep.user.get(user_id)
    except NotFoundError:
        zep.user.add(user_id=user_id)
    try:
        zep.thread.get(thread_id)
    except NotFoundError:
        zep.thread.create(thread_id=thread_id, user_id=user_id)

def retry_on_exception(max_retries=3, delay=2):
    """Lightweight retry decorator to avoid external dependencies like tenacity."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise e
                    print(f"   ⚠️  Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                    time.sleep(delay)
        return wrapper
    return decorator

@retry_on_exception(max_retries=3, delay=1)
def safe_llm_invoke(llm, messages):
    return llm.invoke(messages)

@retry_on_exception(max_retries=2, delay=1)
def safe_search_invoke(tool, query):
    return tool.invoke(query)

# ---------------------------
# 3. MODEL & TOOLS
# ---------------------------
def get_llm() -> ChatGroq:
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0.3,
        api_key=GROQ_API_KEY,
    )

def get_search_tool(max_results: int) -> TavilySearchResults:
    return TavilySearchResults(max_results=max_results)

# ---------------------------
# 4. AGENTS
# ---------------------------
def searcher_agent(state: ResearchState) -> dict[str, Any]:
    print(f"\n🔍 --- Searcher: Finding data for '{state['topic']}' ---")
    search_tool = get_search_tool(state["source_count"])
    results = safe_search_invoke(search_tool, state["topic"])
    sources = [
        {"title": r.get("title", "Unknown"), "url": r.get("url", ""), "content": str(r.get("content", ""))}
        for r in results
    ]

    try:
        zep = get_zep_client()
        zep.thread.add_messages(
            thread_id=state["thread_id"],
            messages=[
                Message(role="user", content=f"Researching: {state['topic']}"),
                Message(role="assistant", content=f"Found {len(sources)} sources.")
            ]
        )
    except Exception as e:
        print(f"   📉 Zep Log Warning: {e}")

    return {"search_results": sources}

def summarizer_agent(state: ResearchState) -> dict[str, Any]:
    print(f"📝 --- Summarizer: Processing {len(state['search_results'])} results ---")
    llm = get_llm()
    summaries = []
    for source in state["search_results"]:
        content = source["content"][:1500]  # Limit context window
        res = safe_llm_invoke(llm, [
            SystemMessage(content="Summarize the following text in exactly 2 concise sentences. Focus on key facts and data."),
            HumanMessage(content=content)
        ])
        summaries.append(res.content)
    return {"summaries": summaries}

def context_retriever_agent(state: ResearchState) -> dict[str, Any]:
    print("🧠 --- Context Agent: Fetching Graph Intelligence ---")
    zep_context = ""
    try:
        zep = get_zep_client()
        # Note: Method name may vary by zep-cloud version. Fallback safely.
        response = zep.graph.get_user_context(user_id=state["user_id"])
        zep_context = getattr(response, "context", "") or ""
    except Exception as e:
        print(f"   📉 Graph Retrieval Warning: {e}")
    return {"zep_context": zep_context}

def writer_agent(state: ResearchState) -> dict[str, Any]:
    print("✍️ --- Writer: Generating final report ---")
    llm = get_llm()
    summaries_block = "\n".join(state["summaries"])[:5000]
    past_context = state["zep_context"][:1500]
    citation_instruction = "Include inline citations [Source URL] where applicable." if state["include_citations"] else "Do not include citations."

    prompt = f"""
Topic: {state['topic']}
Length: {state['report_length']}
Tone: {state['tone']}
{citation_instruction}
Previous Context: {past_context}
Summaries:
{summaries_block}
"""
    response = safe_llm_invoke(llm, [
        SystemMessage(content="You are an expert technical researcher. Write a formal, well-structured report based strictly on the provided findings. Adhere strictly to the requested tone and length."),
        HumanMessage(content=prompt.strip())
    ])
    return {"final_report": response.content}

# ---------------------------
# 5. GRAPH BUILDER & RUNNER
# ---------------------------
def build_research_graph():
    workflow = StateGraph(ResearchState)
    workflow.add_node("searcher", searcher_agent)
    workflow.add_node("summarizer", summarizer_agent)
    workflow.add_node("context_retriever", context_retriever_agent)
    workflow.add_node("writer", writer_agent)

    workflow.set_entry_point("searcher")
    workflow.add_edge("searcher", "summarizer")
    workflow.add_edge("summarizer", "context_retriever")
    workflow.add_edge("context_retriever", "writer")
    workflow.add_edge("writer", END)
    return workflow.compile()

def run_research(
    topic: str,
    source_count: int = 2,
    report_length: str = "Standard",
    tone: str = "Technical",
    include_citations: bool = True,
    user_id: str = "researcher_vasan",
    thread_id: str | None = None,
) -> ResearchState:
    thread_id = thread_id or f"thread_{uuid.uuid4().hex[:6]}"
    ensure_zep_user_and_thread(user_id, thread_id)

    app = build_research_graph()
    return app.invoke({
        "topic": topic,
        "search_results": [],
        "summaries": [],
        "final_report": "",
        "source_count": source_count,
        "report_length": report_length,
        "tone": tone,
        "include_citations": include_citations,
        "user_id": user_id,
        "thread_id": thread_id,
        "zep_context": "",
    })

# ---------------------------
# 6. EXECUTION
# ---------------------------
if __name__ == "__main__":
    result = run_research(
        topic="Impact of OpenAI o1 on coding agents",
        source_count=2,
        report_length="Standard",
        tone="Technical",
        include_citations=True,
        user_id="researcher_vasan"
    )

    print("\n" + "="*60)
    print("📄 FINAL REPORT")
    print("="*60)
    print(result["final_report"])
    print("="*60)
from typing import TypedDict, Annotated, List
import operator
from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.messages import HumanMessage, SystemMessage
import os

# ─── State ────────────────────────────────────────────────────────────────────

class ResearchState(TypedDict):
    topic: str
    search_results: Annotated[List[str], operator.add]
    summaries: Annotated[List[str], operator.add]
    final_report: str

# ─── LLM & Tools ──────────────────────────────────────────────────────────────

def get_llm():
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=os.environ["GROQ_API_KEY"],
        temperature=0.3,
    )

def get_search_tool():
    return TavilySearchResults(
        max_results=5,
        api_key=os.environ["TAVILY_API_KEY"],
    )

# ─── Agent 1: Searcher ─────────────────────────────────────────────────────────

def searcher_agent(state: ResearchState) -> ResearchState:
    """Searches the web for information on the topic."""
    print(f"\n🔍 Searcher Agent: Searching for '{state['topic']}'...")

    search_tool = get_search_tool()
    results = search_tool.invoke(state["topic"])

    # Extract content from results
    contents = []
    for r in results:
        if isinstance(r, dict):
            content = r.get("content", "") or r.get("snippet", "")
            url = r.get("url", "")
            contents.append(f"Source: {url}\n{content}")

    print(f"   ✅ Found {len(contents)} results")
    return {"search_results": contents}

# ─── Agent 2: Summarizer ───────────────────────────────────────────────────────

def summarizer_agent(state: ResearchState) -> ResearchState:
    """Summarizes each search result."""
    print(f"\n📝 Summarizer Agent: Summarizing {len(state['search_results'])} results...")

    llm = get_llm()
    summaries = []

    for i, result in enumerate(state["search_results"]):
        messages = [
            SystemMessage(content="You are a research assistant. Summarize the following web content concisely in 2-3 sentences, keeping only the most important facts."),
            HumanMessage(content=f"Content to summarize:\n\n{result[:2000]}")
        ]
        response = llm.invoke(messages)
        summaries.append(f"[Source {i+1}] {response.content}")
        print(f"   ✅ Summarized source {i+1}")

    return {"summaries": summaries}

# ─── Agent 3: Report Writer ────────────────────────────────────────────────────

def writer_agent(state: ResearchState) -> ResearchState:
    """Writes a comprehensive report from the summaries."""
    print(f"\n✍️  Writer Agent: Writing final report...")

    llm = get_llm()

    summaries_text = "\n\n".join(state["summaries"])

    messages = [
        SystemMessage(content="""You are an expert research report writer.
Write a comprehensive, well-structured research report based on the provided summaries.
Format the report with:
- An executive summary (2-3 sentences)
- Key Findings (3-5 bullet points)
- Detailed Analysis (3-4 paragraphs)
- Conclusion (1-2 sentences)
Make it professional and insightful."""),
        HumanMessage(content=f"Topic: {state['topic']}\n\nResearch Summaries:\n\n{summaries_text}")
    ]

    response = llm.invoke(messages)
    print(f"   ✅ Report written!")
    return {"final_report": response.content}

# ─── Build Graph ───────────────────────────────────────────────────────────────

def build_research_graph():
    graph = StateGraph(ResearchState)

    graph.add_node("searcher", searcher_agent)
    graph.add_node("summarizer", summarizer_agent)
    graph.add_node("writer", writer_agent)

    graph.set_entry_point("searcher")
    graph.add_edge("searcher", "summarizer")
    graph.add_edge("summarizer", "writer")
    graph.add_edge("writer", END)

    return graph.compile()

# ─── Run ───────────────────────────────────────────────────────────────────────

def run_research(topic: str) -> dict:
    graph = build_research_graph()

    initial_state = {
        "topic": topic,
        "search_results": [],
        "summaries": [],
        "final_report": "",
    }

    result = graph.invoke(initial_state)
    return result
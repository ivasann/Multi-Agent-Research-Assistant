# api_server.py — SIMPLE VERSION (no jargon)
import os
import sys
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
import asyncio
import logging

# ✅ AUTO-FIND YOUR AGENTS FILE
# Tries: agents.py → main.py → research.py → pipeline.py
AGENT_MODULE = None
for name in ["agents", "main", "research", "pipeline"]:
    try:
        mod = __import__(name, fromlist=["run_research"])
        if hasattr(mod, "run_research"):
            AGENT_MODULE = mod
            print(f"✅ Loaded research logic from {name}.py")
            break
    except:
        continue

if not AGENT_MODULE:
    print("❌ ERROR: Could not find run_research() in agents.py, main.py, research.py, or pipeline.py")
    print("🔧 Fix: Make sure your LangGraph code has a function called 'run_research'")
    sys.exit(1)

run_research = AGENT_MODULE.run_research
ensure_zep_user_and_thread = getattr(AGENT_MODULE, "ensure_zep_user_and_thread", lambda u,t: None)

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Pydantic models
class ResearchRequest(BaseModel):
    topic: str = Field(..., min_length=3)
    source_count: int = Field(default=3, ge=1, le=10)
    report_length: str = Field(default="Standard")
    tone: str = Field(default="Technical")
    include_citations: bool = Field(default=True)
    user_id: str = Field(default="researcher_vasan")
    thread_id: str = Field(default=None)

class ResearchResponse(BaseModel):
    topic: str
    source_count: int
    search_results: list
    summaries: list
    zep_context: str
    final_report: str
    thread_id: str
    success: bool = True
    error: str = None

# App setup
app = FastAPI(title="Research Agent", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all for local dev
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🔑 CRITICAL: Find index.html reliably on Windows/OneDrive
@app.get("/")
async def home():
    # Try multiple possible locations
    possible_paths = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html"),
        os.path.abspath("index.html"),
        os.path.join(os.getcwd(), "index.html"),
    ]
    for path in possible_paths:
        if os.path.exists(path):
            logger.info(f"📄 Serving index.html from: {path}")
            return FileResponse(path)

    # If not found, show helpful error
    return JSONResponse(
        status_code=404,
        content={
            "error": "index.html not found",
            "checked_paths": possible_paths,
            "cwd": os.getcwd(),
            "files_here": os.listdir(os.getcwd())
        }
    )

@app.post("/research")
async def research(req: ResearchRequest):
    logger.info(f"🔍 Research: '{req.topic}' | {req.source_count} sources | {req.tone}")
    try:
        thread_id = req.thread_id or f"thread_{hash(req.topic) % 10000}"
        ensure_zep_user_and_thread(req.user_id, thread_id)

        # Run in thread pool (LangGraph is sync)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: run_research(
                topic=req.topic,
                source_count=req.source_count,
                report_length=req.report_length,
                tone=req.tone,
                include_citations=req.include_citations,
                user_id=req.user_id,
                thread_id=thread_id
            )
        )
        return ResearchResponse(
            topic=req.topic,
            source_count=req.source_count,
            search_results=result.get("search_results", []),
            summaries=result.get("summaries", []),
            zep_context=result.get("zep_context", ""),
            final_report=result.get("final_report", ""),
            thread_id=thread_id
        )
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return ResearchResponse(
            topic=req.topic,
            source_count=req.source_count,
            search_results=[],
            summaries=[],
            zep_context="",
            final_report=f"Error: {str(e)}",
            thread_id="error",
            success=False,
            error=str(e)
        )

@app.get("/health")
async def health():
    return {"status": "ok", "files": os.listdir(os.getcwd())}

if __name__ == "__main__":
    import uvicorn
    from dotenv import load_dotenv
    load_dotenv()  # Load .env keys
    print("🚀 Server starting at http://127.0.0.1:8000")
    print(f"📁 Working folder: {os.getcwd()}")
    print(f"📄 Files here: {os.listdir('.')}")
    uvicorn.run("api_server:app", host="127.0.0.1", port=8001, reload=False)
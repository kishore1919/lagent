import asyncio
import json
import os
import sys
import datetime
from pathlib import Path
from typing import Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ConfigDict
import requests
import psutil

from mcp_server import register_tools
from dotenv import load_dotenv
from fastmcp import FastMCP

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "9000"))
MCP_BASE_URL = os.getenv("MCP_BASE_URL", f"http://localhost:{MCP_PORT}")

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
INDEX_HTML = STATIC_DIR / "index.html"

if not OPENROUTER_API_KEY:
    print("[WARNING] OPENROUTER_API_KEY not set. Serving frontend in Demo/Simulation Mode.", file=sys.stderr)

APP_STATE: dict[str, Any] = {}


async def _build_tool_list() -> list[dict]:
    mcp = FastMCP("linux-debugger-http")
    register_tools(mcp)
    r = await mcp.list_tools()
    raw: list[dict] = []
    for t in r:
        schema: dict[str, Any] = {"type": "object", "properties": {}}
        try:
            params = t.model_json_schema().get("parameters")
            if isinstance(params, dict):
                schema = params
        except Exception:
            pass
        raw.append({
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description or "Linux system debug tool.",
                "parameters": schema,
            },
        })
    return raw


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        APP_STATE["tools"] = await _build_tool_list()
    except Exception as e:
        print(f"[FATAL] tool initialization failed: {e}", file=sys.stderr)
        raise
    yield
    APP_STATE.clear()


app = FastAPI(
    title="Linux Debugger — OpenRouter Agent",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for development and cross-origin accessibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    tools = APP_STATE.get("tools", [])
    return {
        "status": "ok" if OPENROUTER_API_KEY else "demo",
        "tools_loaded": len(tools),
        "agent_endpoint": "/agent",
        "mcp_base": MCP_BASE_URL,
    }


@app.get("/tools")
async def list_tools():
    tools = APP_STATE.get("tools", [])
    if not tools:
        raise HTTPException(status_code=503, detail="tools not yet initialized")
    return JSONResponse(content=tools)


@app.get("/system_stats")
async def system_stats():
    """Returns actual system statistics for the dashboard telemetry."""
    try:
        # Instantaneous CPU usage percent
        cpu_usage = psutil.cpu_percent(interval=None) or 0.0
        
        # Virtual memory allocation
        vm = psutil.virtual_memory()
        memory_stats = {
            "percent": vm.percent,
            "used": vm.used / 1e9,
            "total": vm.total / 1e9
        }
        
        # Swap allocations
        sm = psutil.swap_memory()
        swap_stats = {
            "percent": sm.percent,
            "used": sm.used / 1e9,
            "total": sm.total / 1e9
        }
        
        # Disk usage percent
        try:
            du = psutil.disk_usage('/')
            disk_stats = {
                "percent": du.percent,
                "used": du.used / 1e9,
                "total": du.total / 1e9
            }
        except Exception:
            disk_stats = {"percent": 0.0, "used": 0.0, "total": 0.0}
            
        # Uptime string parsing
        boot = datetime.datetime.fromtimestamp(psutil.boot_time())
        delta = datetime.datetime.now() - boot
        days, rem = divmod(int(delta.total_seconds()), 86400)
        hours, rem = divmod(rem, 3600)
        minutes, _ = divmod(rem, 60)
        uptime_str = f"{days}d {hours}h {minutes}m"
        
        # CPU/Mem consuming processes list
        procs = []
        try:
            for p in sorted(
                psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]),
                key=lambda p: (p.info["cpu_percent"] or 0),
                reverse=True,
            )[:6]:
                procs.append({
                    "pid": p.info["pid"],
                    "name": p.info["name"] or "?",
                    "cpu": p.info["cpu_percent"] or 0.0,
                    "memory": p.info["memory_percent"] or 0.0
                })
        except Exception:
            pass
            
        return {
            "cpu_usage": cpu_usage,
            "memory": memory_stats,
            "swap": swap_stats,
            "disk": disk_stats,
            "uptime": uptime_str,
            "processes": procs
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to gather system statistics: {e}")


SYSTEM_PROMPT = (
    "You are a Linux system-debug assistant. Use the provided MCP tools "
    "to inspect the real system — do NOT hallucinate numbers or process names. "
    "After each tool result, give a concise, actionable diagnosis."
)


class AgentRequest(BaseModel):
    prompt: str = Field(..., description="Natural-language description of the debug task.")
    stream: bool = Field(default=False)

    model_config = ConfigDict(extra="forbid")


class AgentResponse(BaseModel):
    response: str

    model_config = ConfigDict(extra="forbid")


def _call_llm(messages: list[dict], tools: list[dict]) -> dict:
    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": OPENROUTER_MODEL,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()


def _tool_text(result: Any) -> str:
    parts: list[str] = []
    for c in result.content:
        parts.append(c.text if hasattr(c, "text") else str(c))
    return "\n".join(parts)


async def _call_tool_async(name: str, args: dict) -> Any:
    mcp = FastMCP("linux-debugger-worker")
    register_tools(mcp)
    return await mcp.call_tool(name, args)


def _execute_tool_calls(tool_calls: list[dict]) -> list[str]:
    results: list[str] = []
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        for tc in tool_calls:
            fn = tc.get("function", {})
            name = fn.get("name", "")
            try:
                args = json.loads(fn.get("arguments", "{}") or "{}")
            except json.JSONDecodeError:
                args = {}
            try:
                result = loop.run_until_complete(_call_tool_async(name, args))
                results.append(f"[{name}]\n{_tool_text(result)}\n")
            except Exception as exc:
                results.append(f"[{name}] ERROR: {exc}\n")
    finally:
        loop.close()
    return results


def _run_agent(prompt: str, max_rounds: int = 3) -> str:
    if not OPENROUTER_API_KEY:
        return (
            "**Notice:** Lagent is running in Demo/Simulation Mode because the `OPENROUTER_API_KEY` "
            "is not configured in `.env`. To execute real commands using actual LLM reasoning, "
            "please configure your credentials in the environment and restart the server."
        )
        
    tools = APP_STATE.get("tools", [])
    if not tools:
        return "Error: MCP tools not initialized yet. Wait and retry."

    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    for _round in range(max_rounds):
        data = _call_llm(messages, tools)
        choice = data.get("choices", [{}])[0]
        msg: dict = choice.get("message", {})

        if choice.get("finish_reason") == "stop" or not msg.get("tool_calls"):
            return msg.get("content") or "(no response)"

        messages.append({"role": "assistant", "tool_calls": msg["tool_calls"]})
        outputs = _execute_tool_calls(msg["tool_calls"])

        for tc, out in zip(msg["tool_calls"], outputs):
            messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id", ""),
                "content": out,
            })

    return "Max rounds — last outputs:\n\n" + json.dumps(messages, indent=2)


@app.post("/agent", response_model=AgentResponse)
async def agent(req: AgentRequest):
    try:
        result = await asyncio.get_event_loop().run_in_executor(None, _run_agent, req.prompt)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return AgentResponse(response=result)


@app.post("/invoke", response_model=AgentResponse)
async def invoke(req: AgentRequest):
    return await agent(req)


# Mount static assets using absolute path so they are correct regardless of cwd
os.makedirs(str(STATIC_DIR), exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/")
async def root():
    """Serve the main dashboard UI at the root URL."""
    if not INDEX_HTML.exists():
        raise HTTPException(status_code=404, detail="index.html not found")
    return FileResponse(str(INDEX_HTML))


def main():
    import uvicorn
    uvicorn.run("http_server:app", host=MCP_HOST, port=MCP_PORT, log_level="info")


if __name__ == "__main__":
    main()

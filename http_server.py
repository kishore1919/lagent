import json
import os
import sys
from typing import Any

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field

from mcp_server import register_tools

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "9000"))
MCP_BASE_URL = os.getenv("MCP_BASE_URL", f"http://localhost:{MCP_PORT}")

if not OPENROUTER_API_KEY:
    print("[FATAL] OPENROUTER_API_KEY not set. Populate .env.", file=sys.stderr)
    sys.exit(1)

http_mcp = FastMCP("system-debugger")
register_tools(http_mcp)

app = FastAPI(title="System Debugger Agent API")

_tools_cache: list[dict] | None = None

SYSTEM_PROMPT = (
    "You are a system-debug assistant. Use the provided MCP tools "
    "to inspect the real system — do NOT hallucinate numbers or process names. "
    "After each tool result, give a concise, actionable diagnosis."
)


class AgentRequest(BaseModel):
    prompt: str = Field(..., description="Natural-language description of the debug task.")
    model_config = ConfigDict(extra="forbid")


class AgentResponse(BaseModel):
    response: str


@app.on_event("startup")
async def _warm_tools():
    global _tools_cache
    try:
        _tools_cache = await http_mcp.list_tools()
    except Exception as e:
        print(f"[ERROR] Tool warmup failed: {e}", file=sys.stderr)
        _tools_cache = []


def _make_tools_json() -> list[dict]:
    raw = _tools_cache or []
    if raw and isinstance(raw[0], dict):
        return raw
    out: list[dict] = []
    for t in raw:
        schema: dict[str, Any] = {"type": "object", "properties": {}}
        try:
            maybe = t.model_json_schema().get("parameters")
            if isinstance(maybe, dict):
                schema = maybe
        except Exception:
            pass
        out.append({
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description or "Linux system debug tool.",
                "parameters": schema,
            },
        })
    return out


def _tool_text(result: Any) -> str:
    parts: list[str] = []
    for c in result.content:
        parts.append(c.text if hasattr(c, "text") else str(c))
    return "\n".join(parts)


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


async def _run_agent(prompt: str, max_rounds: int = 3) -> str:
    import asyncio

    tools = _make_tools_json()
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    for _round in range(max_rounds):
        data = await asyncio.to_thread(_call_llm, messages, tools)
        choice = data.get("choices", [{}])[0]
        msg: dict = choice.get("message", {})
        if choice.get("finish_reason") == "stop" or not msg.get("tool_calls"):
            return msg.get("content") or "(no response)"
        messages.append({"role": "assistant", "tool_calls": msg["tool_calls"]})
        for tc in msg["tool_calls"]:
            fn = tc.get("function", {})
            name = fn.get("name", "")
            try:
                args = json.loads(fn.get("arguments", "{}") or "{}")
            except json.JSONDecodeError:
                args = {}
            try:
                result = await http_mcp.call_tool(name, args)
                content = _tool_text(result)
            except Exception as exc:
                content = f"ERROR: {exc}"
            messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id", ""),
                "content": f"[{name}]\n{content}\n",
            })
    return "Max rounds — last outputs:\n\n" + json.dumps(messages, indent=2)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "mcp_endpoint": f"{MCP_BASE_URL}/mcp",
        "agent_endpoint": f"{MCP_BASE_URL}/agent",
    }


@app.get("/tools")
def list_tools():
    return JSONResponse(content=_make_tools_json())


@app.post("/agent", response_model=AgentResponse)
async def agent(req: AgentRequest):
    try:
        result = await _run_agent(req.prompt)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return AgentResponse(response=result)


def main():
    import uvicorn

    uvicorn.run("http_server:app", host=MCP_HOST, port=MCP_PORT, log_level="info")


if __name__ == "__main__":
    main()

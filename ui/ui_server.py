"""
JARVIS Web UI Server
====================
FastAPI server at http://localhost:3000 that provides a browser-based
interface to the JARVIS voice assistant.

Features:
  - WebSocket /ws/chat  — real-time text conversation with JARVIS
  - GET  /status        — health check + JARVIS status
  - GET  /memory        — list all stored Supabase memory entries
  - POST /memory        — store a new fact {key, value}
  - Static files at /   — serves the React-free HTML dashboard

Run:
    .venv\Scripts\python.exe ui/ui_server.py
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from typing import Optional

# ---------------------------------------------------------------------------
# Add assistant\ to path so we can import brain / router / memory directly.
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_ASSISTANT_DIR = os.path.join(os.path.dirname(_HERE), "assistant")
_PROJECT_ROOT = os.path.dirname(_HERE)

if _ASSISTANT_DIR not in sys.path:
    sys.path.insert(0, _ASSISTANT_DIR)

# Load .env before importing anything that reads env vars.
from dotenv import load_dotenv
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Lazy-import JARVIS components (they take a moment to warm up).
# ---------------------------------------------------------------------------
from brain import JarvisBrain
from memory import JarvisMemory
from router import JarvisRouter

# ---------------------------------------------------------------------------
# App + state
# ---------------------------------------------------------------------------
app = FastAPI(title="JARVIS Web UI", version="1.0.0")

_brain: Optional[JarvisBrain] = None
_router: Optional[JarvisRouter] = None
_memory: Optional[JarvisMemory] = None
_start_time = time.time()
_conversation_log: list[dict] = []   # in-memory log for dashboard


def _get_router() -> JarvisRouter:
    global _brain, _router, _memory
    if _router is None:
        _brain = JarvisBrain()
        _router = JarvisRouter(brain=_brain)
        _memory = _router.memory
    return _router


# ---------------------------------------------------------------------------
# Static files (dashboard HTML)
# ---------------------------------------------------------------------------
_STATIC_DIR = os.path.join(_HERE, "static")
os.makedirs(_STATIC_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    index = os.path.join(_STATIC_DIR, "index.html")
    with open(index, "r", encoding="utf-8") as fh:
        return HTMLResponse(content=fh.read())


# ---------------------------------------------------------------------------
# Status endpoint
# ---------------------------------------------------------------------------
@app.get("/status")
async def get_status():
    return {
        "status": "online",
        "model": _brain.model if _brain else "qwen3:4b",
        "uptime_seconds": int(time.time() - _start_time),
        "memory_enabled": _memory.available if _memory else False,
        "timestamp": datetime.now().isoformat(),
    }


# ---------------------------------------------------------------------------
# Memory endpoints
# ---------------------------------------------------------------------------
@app.get("/memory")
async def list_memory():
    router = _get_router()
    entries = router.memory.list_all()
    return {"entries": entries}


class MemoryPayload(BaseModel):
    key: str
    value: str


@app.post("/memory")
async def store_memory(payload: MemoryPayload):
    router = _get_router()
    ok = router.memory.store(payload.key, payload.value)
    if not ok:
        raise HTTPException(
            status_code=503,
            detail="Supabase not configured. Add credentials to .env"
        )
    return {"stored": True, "key": payload.key, "value": payload.value}


# ---------------------------------------------------------------------------
# WebSocket chat endpoint
# ---------------------------------------------------------------------------
@app.websocket("/ws/chat")
async def websocket_chat(ws: WebSocket):
    await ws.accept()

    router = _get_router()

    # Send welcome message
    await ws.send_json({
        "role": "assistant",
        "text": "Good day, sir. JARVIS Web Interface is online. How may I assist you?",
        "timestamp": datetime.now().isoformat(),
    })

    try:
        while True:
            data = await ws.receive_text()

            try:
                payload = json.loads(data)
                user_text = payload.get("text", "").strip()
            except (json.JSONDecodeError, AttributeError):
                user_text = str(data).strip()

            if not user_text:
                continue

            # Log user turn
            user_entry = {
                "role": "user",
                "text": user_text,
                "timestamp": datetime.now().isoformat(),
            }
            _conversation_log.append(user_entry)
            await ws.send_json(user_entry)

            # Send "thinking" signal
            await ws.send_json({"role": "thinking", "text": ""})

            # Run router in thread pool (it calls Ollama which is blocking)
            loop = asyncio.get_event_loop()
            reply = await loop.run_in_executor(
                None, router.route, user_text
            )

            # Log assistant reply
            reply_entry = {
                "role": "assistant",
                "text": reply or "I didn't catch that, sir.",
                "timestamp": datetime.now().isoformat(),
            }
            _conversation_log.append(reply_entry)

            await ws.send_json(reply_entry)

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await ws.send_json({
                "role": "error",
                "text": f"Error: {exc}",
                "timestamp": datetime.now().isoformat(),
            })
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Conversation log endpoint
# ---------------------------------------------------------------------------
@app.get("/log")
async def get_log(limit: int = 50):
    return {"log": _conversation_log[-limit:]}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    print("=" * 50)
    print("JARVIS WEB UI SERVER")
    print("=" * 50)
    print(f"  Dashboard : http://localhost:3000")
    print(f"  WebSocket : ws://localhost:3000/ws/chat")
    print(f"  Status    : http://localhost:3000/status")
    print(f"  Memory    : http://localhost:3000/memory")
    print("=" * 50)

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=3000,
        log_level="warning",
    )

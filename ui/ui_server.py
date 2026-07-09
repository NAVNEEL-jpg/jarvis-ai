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
# Control Panel Configuration Endpoints
# ---------------------------------------------------------------------------
class ConfigPayload(BaseModel):
    amazon_email: str
    amazon_password: str
    alexa_region: str
    google_home_email: str
    google_home_password: str
    supabase_url: str
    supabase_anon_key: str

def update_env_file(updates: dict[str, str]):
    env_path = os.path.join(_PROJECT_ROOT, ".env")
    lines = []
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    written = set()
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            new_lines.append(line)
            continue
        if "=" in stripped:
            k = stripped.split("=")[0].strip()
            if k in updates:
                new_lines.append(f"{k}={updates[k]}\n")
                written.add(k)
                continue
        new_lines.append(line)
    for k, v in updates.items():
        if k not in written:
            new_lines.append(f"{k}={v}\n")
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

@app.get("/api/config")
async def get_config():
    load_dotenv(os.path.join(_PROJECT_ROOT, ".env"), override=True)
    return {
        "amazon_email": os.getenv("AMAZON_EMAIL", ""),
        "alexa_region": os.getenv("ALEXA_REGION", "amazon.in"),
        "google_home_email": os.getenv("GOOGLE_HOME_EMAIL", ""),
        "supabase_url": os.getenv("SUPABASE_URL", ""),
        # Hide passwords/keys for safety but indicate presence
        "has_amazon_password": bool(os.getenv("AMAZON_PASSWORD")),
        "has_google_home_password": bool(os.getenv("GOOGLE_HOME_PASSWORD")),
        "has_supabase_anon_key": bool(os.getenv("SUPABASE_ANON_KEY")),
    }

@app.post("/api/config")
async def save_config(payload: ConfigPayload):
    updates = {
        "AMAZON_EMAIL": payload.amazon_email,
        "ALEXA_REGION": payload.alexa_region,
        "GOOGLE_HOME_EMAIL": payload.google_home_email,
        "SUPABASE_URL": payload.supabase_url,
    }
    if payload.amazon_password:
        updates["AMAZON_PASSWORD"] = payload.amazon_password
    if payload.google_home_password:
        updates["GOOGLE_HOME_PASSWORD"] = payload.google_home_password
    if payload.supabase_anon_key:
        updates["SUPABASE_ANON_KEY"] = payload.supabase_anon_key

    try:
        update_env_file(updates)
        # Reload environment
        load_dotenv(os.path.join(_PROJECT_ROOT, ".env"), override=True)
        # Force re-initialization of backend router/trainer next time
        global _router
        _router = None
        return {"success": True}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

# ---------------------------------------------------------------------------
# Training Commands Endpoints
# ---------------------------------------------------------------------------
class TrainingPayload(BaseModel):
    trigger: str
    response: str
    category: str = "general"

@app.get("/api/training")
async def get_training_commands():
    router = _get_router()
    return {"commands": router.trainer.get_commands()}

@app.post("/api/training")
async def add_training_command(payload: TrainingPayload):
    router = _get_router()
    res = router.trainer.add_command(payload.trigger, payload.response, payload.category)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res

@app.delete("/api/training/{command_id}")
async def delete_training_command(command_id: int):
    router = _get_router()
    ok = router.trainer.delete_command(command_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Failed to delete command.")
    return {"success": True}

@app.post("/api/training/{command_id}/toggle")
async def toggle_training_command(command_id: int, enabled: bool):
    router = _get_router()
    ok = router.trainer.toggle_command(command_id, enabled)
    if not ok:
        raise HTTPException(status_code=400, detail="Failed to toggle command.")
    return {"success": True}

# ---------------------------------------------------------------------------
# Smart Home Devices Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/devices")
async def list_devices():
    router = _get_router()
    devices = []
    # 1. Alexa devices
    if router.home.alexa.available and router.home.alexa._ready:
        smart = router.home.alexa.list_smart_home()
        devices.extend([{"name": d, "type": "Alexa Device"} for d in smart])
    # 2. Google Home devices
    if router.home.google.available and router.home.google._ready:
        gdevices = router.home.google.list_devices()
        devices.extend([{"name": gd, "type": "Google Home"} for gd in gdevices])
    # 3. Home Assistant devices
    if router.home.ha.available:
        entities = router.home.ha.list_entities("light") + router.home.ha.list_entities("switch")
        devices.extend([{"name": e.split(".")[-1].replace("_", " "), "type": "Home Assistant"} for e in entities])
    return {"devices": devices}

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


def get_local_ip() -> str:
    """Return the local network IP address of this machine."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    local_ip = get_local_ip()

    print("=" * 60)
    print("JARVIS WEB UI SERVER")
    print("=" * 60)
    print(f"  Local Dashboard   : http://localhost:3000")
    print(f"  Wi-Fi Network URL : http://{local_ip}:3000")
    print(f"  WebSocket         : ws://{local_ip}:3000/ws/chat")
    print(f"  Status Endpoint   : http://{local_ip}:3000/status")
    print("-" * 60)
    print("  To access JARVIS from mobiles or laptops:")
    print("  1. Connect them to the SAME Wi-Fi network.")
    print(f"  2. Open the URL: http://{local_ip}:3000 in the browser.")
    print("  Note: If connection fails, make sure Python is allowed")
    print("  through your Windows Defender Firewall settings.")
    print("=" * 60)

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=3000,
        log_level="warning",
    )

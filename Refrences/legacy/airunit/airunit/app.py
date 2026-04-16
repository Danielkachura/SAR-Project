import asyncio
import json
import re
from pathlib import Path
from typing import Dict, Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from scan_manager import ScanManager, WORKDIR
from ble_scan_manager import BleScanManager

LOGDIR = WORKDIR / "logs"
DESCRIPTIONS_FILE = LOGDIR / "scan_descriptions.json"
CONFIG_FILE = Path(__file__).parent / "config.py"


def write_config_file(hop_cfg):
    """Directly update config.py file with hopping settings."""
    config_text = CONFIG_FILE.read_text()
    
    if hop_cfg.mode == "hopping":
        config_text = re.sub(
            r"HOP_ENABLED = (True|False)",
            "HOP_ENABLED = True",
            config_text
        )
        channels_str = str(hop_cfg.channels)
        config_text = re.sub(
            r"HOP_CHANNELS = \[.*?\]",
            f"HOP_CHANNELS = {channels_str}",
            config_text
        )
        config_text = re.sub(
            r"HOP_INTERVAL_SEC = [0-9.]+",
            f"HOP_INTERVAL_SEC = {hop_cfg.interval_sec}",
            config_text
        )
    else:
        config_text = re.sub(
            r"HOP_ENABLED = (True|False)",
            "HOP_ENABLED = False",
            config_text
        )
        config_text = re.sub(
            r"HOP_BASE_CHANNEL = [0-9]+",
            f"HOP_BASE_CHANNEL = {hop_cfg.fixed_channel}",
            config_text
        )
    
    CONFIG_FILE.write_text(config_text)


def load_descriptions():
    if DESCRIPTIONS_FILE.exists():
        try:
            return json.loads(DESCRIPTIONS_FILE.read_text())
        except Exception:
            return {}
    return {}


def save_descriptions(descriptions):
    LOGDIR.mkdir(exist_ok=True, parents=True)
    DESCRIPTIONS_FILE.write_text(json.dumps(descriptions, indent=2))

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

clients = set()
_event_loop: Optional[asyncio.AbstractEventLoop] = None  # filled at startup


@app.on_event("startup")
async def _capture_loop():
    global _event_loop
    _event_loop = asyncio.get_running_loop()


async def _broadcast(msg: Dict[str, Any]):
    dead = []
    for ws in list(clients):
        try:
            await ws.send_text(json.dumps(msg))
        except Exception:
            dead.append(ws)
    for ws in dead:
        clients.discard(ws)


def broadcast(msg: Dict[str, Any]):
    """
    Safe to call from worker threads. Schedules _broadcast on the main event loop.
    """
    if _event_loop is None or _event_loop.is_closed():
        return
    asyncio.run_coroutine_threadsafe(_broadcast(msg), _event_loop)


manager = ScanManager(
    on_output=lambda line, count: (
        broadcast({"type": "log", "line": line, "count": count}),
        broadcast({"type": "status", "status": f"running({count})"}),
    ),
    on_exit=lambda code: broadcast({"type": "status", "status": f"exited({code})", "code": code}),
)

ble_manager = BleScanManager(
    on_output=lambda line, count: (
        broadcast({"type": "ble_log", "line": line, "count": count}),
        broadcast({"type": "ble_status", "status": f"running({count})"}),
    ),
    on_exit=lambda code: broadcast({"type": "ble_status", "status": f"exited({code})", "code": code}),
)


class HopConfig(BaseModel):
    mode: str = Field("fixed", description="hopping or fixed")
    channels: list[int] = Field(default_factory=lambda: [1, 6, 11])
    interval_sec: float = 0.5
    fixed_channel: int = 1


hop_config = HopConfig()


@app.get("/")
def index():
    return HTMLResponse((Path(__file__).parent / "static" / "index.html").read_text())


@app.post("/logs/delete")
def delete_log_file(filename: str = ""):
    if not filename:
        return {"ok": False, "error": "filename required"}
    
    # Prevent directory traversal
    if ".." in filename or filename.startswith("/"):
        return {"ok": False, "error": "invalid filename"}
    
    file_path = LOGDIR / filename
    if not file_path.exists():
        return {"ok": False, "error": "file not found"}
    
    try:
        file_path.unlink()
        broadcast({"type": "log", "line": f"[file] Deleted {filename}"})
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/logs")
def list_logs():
    LOGDIR.mkdir(exist_ok=True, parents=True)
    descriptions = load_descriptions()
    files = []
    for p in sorted(LOGDIR.glob("*"), key=lambda x: x.stat().st_mtime, reverse=True):
        if p.name == "scan_descriptions.json":  # Skip the descriptions file itself
            continue
        files.append(
            {
                "name": p.name,
                "size_bytes": p.stat().st_size,
                "mtime": p.stat().st_mtime,
                "description": descriptions.get(p.name, ""),
            }
        )
    return {"files": files}


@app.get("/logs/{fname}")
def download(fname: str):
    path = LOGDIR / fname
    if not path.exists():
        return {"error": "not found"}
    return FileResponse(path)


@app.post("/scan/start")
def start_scan():
    ok = manager.start()
    if ok:
        broadcast({"type": "status", "status": "running(0)"})
    return {"started": ok, "status": manager.status()}


@app.post("/scan/stop")
def stop_scan():
    ok = manager.stop()
    return {"stopped": ok, "status": manager.status()}


@app.get("/scan/status")
def scan_status():
    return {"status": manager.status()}


@app.post("/ble/scan/start")
def start_ble_scan():
    ok = ble_manager.start()
    if ok:
        broadcast({"type": "ble_status", "status": "running(0)"})
    return {"started": ok, "status": ble_manager.status()}


@app.post("/ble/scan/stop")
def stop_ble_scan():
    ok = ble_manager.stop()
    return {"stopped": ok, "status": ble_manager.status()}


@app.get("/ble/scan/status")
def ble_scan_status():
    return {"status": ble_manager.status()}


@app.get("/config/hopping")
def get_hop_config():
    return hop_config.model_dump()


@app.post("/config/hopping")
def set_hop_config(cfg: HopConfig):
    global hop_config
    hop_config = cfg
    write_config_file(cfg)
    return {"ok": True, **cfg.model_dump()}


@app.get("/logs/description/{fname}")
def get_description(fname: str):
    descriptions = load_descriptions()
    return {"filename": fname, "description": descriptions.get(fname, "")}


class DescriptionUpdate(BaseModel):
    filename: str
    description: str


@app.post("/logs/description")
def update_description(update: DescriptionUpdate):
    descriptions = load_descriptions()
    descriptions[update.filename] = update.description
    save_descriptions(descriptions)
    return {"ok": True, "filename": update.filename, "description": update.description}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    try:
        await ws.send_text(json.dumps({"type": "status", "status": manager.status()}))
        while True:
            await ws.receive_text()  # keep alive / ignore messages
    except WebSocketDisconnect:
        pass
    finally:
        clients.discard(ws)

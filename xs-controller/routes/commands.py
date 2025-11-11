from fastapi import APIRouter, HTTPException
from aiomqtt import Client
from sqlmodel import Session
from models_ext import CommandLog, engine
import json, logging, uuid, datetime

router = APIRouter()
log = logging.getLogger("Commands")

@router.post("/send")
async def send_command(payload: dict):
    """Send command to a specific Edge."""
    edge_id = payload.get("edge_id")
    command = payload.get("command")
    if not edge_id or not command:
        raise HTTPException(400, "Missing edge_id or command")

    cmd_id = str(uuid.uuid4())
    msg = {
        "cmd_id": cmd_id,
        "edge_id": edge_id,
        "type": "command",
        "action": command.get("action", "reload_rules"),
        "params": command.get("params", {}),
        "timestamp": datetime.datetime.utcnow().isoformat(),
    }

    # Log to DB
    with Session(engine) as s:
        s.add(CommandLog(cmd_id=cmd_id, edge_id=edge_id, command=msg))
        s.commit()

    try:
        async with Client("broker.hivemq.com", 8000, transport="websockets", websocket_path="/mqtt") as client:
            await client.publish(f"xsctrl/commands/{edge_id}", json.dumps(msg).encode())
            log.info(f"[CMD] Sent to {edge_id}: {msg}")
    except Exception as e:
        raise HTTPException(500, str(e))

    return {"cmd_id": cmd_id, "status": "sent"}

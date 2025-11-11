from fastapi import APIRouter
import json, logging
from aiomqtt import Client

router = APIRouter()
log = logging.getLogger("Commands")

@router.post("/send")
async def send_command(payload: dict):
    edge_id = payload.get("edge_id")
    command = payload.get("command")
    if not edge_id or not command:
        return {"error": "missing edge_id or command"}
    async with Client("test.mosquitto.org") as client:
        topic = f"xsctrl/commands/{edge_id}"
        await client.publish(topic, json.dumps(command))
        log.info(f"[CMD] {edge_id} → {command}")
    return {"status": "sent", "topic": topic}

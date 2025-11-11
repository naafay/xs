import json, logging, os
from fastapi import APIRouter, HTTPException, Request
from mqtt_server import MQTTServer
from aiomqtt import Client
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger("Rules")
router = APIRouter()

MQTT_BROKER = os.getenv("MQTT_BROKER", "broker.hivemq.com")
MQTT_PORT = int(os.getenv("MQTT_PORT", 8000))  # WebSocket port

@router.post("/push")
async def push_rules(request: Request):
    """
    Push updated rule sets to one or multiple edges.
    Accepts:
    {
        "edge_id": "xsedge-001",             # optional
        "edges": ["xsedge-001","xsedge-002"],# optional
        "broadcast": true,                   # optional, send to all
        "rules": [ {...}, {...} ]
    }
    """
    try:
        payload = await request.json()
        edges = payload.get("edges", [])
        edge_id = payload.get("edge_id")
        broadcast = payload.get("broadcast", False)
        rules = payload.get("rules")

        # --- validation ---
        if not rules or (not edges and not edge_id and not broadcast):
            raise HTTPException(400, "edge_id or rules missing")

        # Normalize edges list
        target_edges = set()
        if edge_id:
            target_edges.add(edge_id)
        if edges:
            target_edges.update(edges)

        # --- save rules locally ---
        rules_path = "rules_latest.json"
        with open(rules_path, "w") as f:
            json.dump(rules, f, indent=2)
        log.info(f"[Rules] Saved new ruleset → {rules_path}")

        # --- publish ruleset ---
        published = []
        async with Client(
            MQTT_BROKER,
            MQTT_PORT,
            transport="websockets",
            websocket_path="/mqtt"
        ) as client:
            # individual edge pushes
            for eid in target_edges:
                topic = f"xsctrl/rules/{eid}"
                await client.publish(topic, json.dumps(rules).encode())
                published.append(topic)
                log.info(f"[Rules] Published {len(rules)} rules to {topic}")

            # broadcast (if requested)
            if broadcast:
                topic = "xsctrl/rules/all"
                await client.publish(topic, json.dumps(rules).encode())
                published.append(topic)
                log.info(f"[Rules] Broadcasted {len(rules)} rules to all edges")

        return {
            "status": "published",
            "targets": list(target_edges) if target_edges else ["ALL"],
            "rule_count": len(rules),
            "topics": published
        }

    except Exception as e:
        log.error(f"[Rules] Push failed: {e}")
        raise HTTPException(500, f"Push failed: {e}")

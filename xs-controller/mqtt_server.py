import asyncio, json, logging, datetime
from aiomqtt import Client, MqttError
from sqlmodel import Session, select
from models import Telemetry, engine

log = logging.getLogger("MQTTServer")

class MQTTServer:
    def __init__(self, broker="broker.hivemq.com", port=8000):
        self.broker, self.port = broker, port

    async def listen_and_store(self, ws_clients:set):
        """
        Listen to MQTT messages from xsedge/# and store telemetry.
        Compatible with aiomqtt >= 2.3.
        """
        while True:
            try:
                async with Client(
                    self.broker,
                    self.port,
                    transport="websockets",
                    websocket_path="/mqtt"
                ) as client:

                    await client.subscribe("xsedge/#")
                    log.info(f"[MQTT] Subscribed xsedge/# on {self.broker}:{self.port}")

                    # Direct iteration over client.messages
                    async for msg in client.messages:
                        log.debug(f"[MQTT] Incoming topic: {msg.topic}")

                        if str(msg.topic) == "xsedge/register":
                            try:
                                payload = json.loads(msg.payload.decode())
                                edge_id = payload.get("edge_id")
                                version = payload.get("version", "unknown")
                                from models import Edge
                                from sqlmodel import Session, select
                                with Session(engine) as s:
                                    edge = s.exec(select(Edge).where(Edge.edge_id == edge_id)).first()
                                    if not edge:
                                        edge = Edge(edge_id=edge_id, version=version)
                                        s.add(edge)
                                    edge.last_seen = datetime.datetime.utcnow()
                                    edge.status = "ONLINE"
                                    s.commit()
                                log.info(f"[REGISTER] Edge {edge_id} registered (v{version})")
                                continue  # skip normal telemetry saving for this message
                            except Exception as e:
                                log.error(f"[REGISTER] Error processing registration: {e}")
                                continue
                        try:
                            payload = json.loads(msg.payload.decode())
                            edge_id = payload.get("edge_id")
                            data = payload.get("data", {})
                            topic = payload.get("topic", "unknown")
                            await self._save(edge_id, topic, data)
                            await self._broadcast(ws_clients, payload)
                        except Exception as e:
                            log.error(f"[MQTT] payload error: {e}")

            except MqttError as e:
                log.error(f"[MQTT] broker error {e}, retrying in 5 s")
                await asyncio.sleep(5)
            except Exception as e:
                log.error(f"[MQTT] general error: {e}")
                await asyncio.sleep(5)

    async def _save(self, edge_id, topic, data):
            """Persist telemetry to SQLite."""
            log.info(f"[MQTT] saved telemetry from {edge_id} topic={topic} data={data}")
            
            if not edge_id:
                return
            with Session(engine) as s:
                rec = Telemetry(edge_id=edge_id, topic=topic, data=json.dumps(data))
                s.add(rec)
                s.commit()

            # ✅ ACK handling
            if "ack" in topic:
                from models_ext import CommandLog
                with Session(engine) as s:
                    cmd_id = data.get("cmd_id")
                    entry = s.exec(select(CommandLog).where(CommandLog.cmd_id == cmd_id)).first()
                    if entry:
                        entry.status = "ACK"
                        entry.result = data.get("result", "")
                        entry.ts_ack = datetime.datetime.utcnow()
                        s.add(entry)
                        s.commit()
                        log.info(f"[ACK] Command {cmd_id} acknowledged: {entry.result}")

    async def _broadcast(self, ws_clients:set, payload):
        """Push telemetry to connected WebSocket clients."""
        dead = []
        for ws in ws_clients:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for d in dead:
            ws_clients.discard(d)

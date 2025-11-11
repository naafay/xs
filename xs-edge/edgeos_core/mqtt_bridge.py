import asyncio, json, logging, random, sys
from aiomqtt import Client, MqttError

log = logging.getLogger("MQTTBridge")

class MQTTBridge:
    """
    MQTT Bridge for XS Edge ↔ Controller communication.
    Works with aiomqtt >=2.0.
    """

    def __init__(self, broker="broker.hivemq.com", port=1883, edge_id=None):
        self.broker = broker
        self.port = port
        self.edge_id = edge_id or f"xsedge-{random.randint(1000,9999)}"
        self.client = None
        self.running = False
        self.connected = asyncio.Event()

        # Fix for Windows event loop
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # ───────────────────────────────────────────────
    async def connect(self):
        """Establish persistent connection to MQTT broker."""
        try:
            log.info(f"[Bridge] Connecting to MQTT broker {self.broker}:{self.port} as {self.edge_id}...")
            # aiomqtt connects automatically on entering the async context
            self.client = Client(self.broker, self.port)
            self.client._client_id = self.edge_id.encode()  # assign client ID manually
            self.running = True
            self.connected.set()
            log.info("[Bridge] Connected to broker ✅")
        except MqttError as e:
            log.error(f"[Bridge] Connection failed: {e}")
            self.running = False

    # ───────────────────────────────────────────────
    async def publish(self, topic, data):
        """Publish JSON message to MQTT broker."""
        if not self.running:
            log.warning("[Bridge] Publish attempted before connection.")
            return
        try:
            async with Client(self.broker, self.port, transport="websockets", websocket_path="/mqtt") as client:

                client._client_id = self.edge_id.encode()
                payload = json.dumps({"edge_id": self.edge_id, "topic": topic, "data": data})
                await client.publish(f"xsedge/{self.edge_id}/{topic}", payload.encode())
                log.debug(f"[Bridge] Published → xsedge/{self.edge_id}/{topic}")
        except Exception as e:
            log.error(f"[Bridge] Publish failed: {e}")

    # ───────────────────────────────────────────────
    async def subscribe(self, topic_filter="xsctrl/commands/#", callback=None):
        """Subscribe to controller commands."""
        try:
            async with Client(self.broker, self.port, transport="websockets", websocket_path="/mqtt") as client:

                client._client_id = self.edge_id.encode()
                async with client.messages() as messages:
                    await client.subscribe(topic_filter)
                    log.info(f"[Bridge] Subscribed to {topic_filter}")
                    async for msg in messages:
                        try:
                            payload = json.loads(msg.payload.decode())
                            log.info(f"[Bridge] Received command: {payload}")
                            if callback:
                                await callback(payload)
                        except Exception as e:
                            log.error(f"[Bridge] Error handling message: {e}")
        except Exception as e:
            log.error(f"[Bridge] Subscribe loop error: {e}")

    # ───────────────────────────────────────────────
    async def disconnect(self):
        """Gracefully close connection."""
        try:
            self.running = False
            log.info("[Bridge] Disconnected from broker")
        except Exception as e:
            log.warning(f"[Bridge] Disconnect error: {e}")

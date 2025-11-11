import asyncio, json, logging, random
from asyncio_mqtt import Client, MqttError

log = logging.getLogger("MQTTBridge")

class MQTTBridge:
    """
    MQTT Bridge for XS Edge ↔ Controller communication.
    Optional connector that relays DataBus messages to/from broker topics.
    """

    def __init__(self, broker="test.mosquitto.org", port=1883, edge_id=None):
        self.broker = broker
        self.port = port
        self.edge_id = edge_id or f"xsedge-{random.randint(1000,9999)}"
        self.client = None
        self.running = False
        self.connected = asyncio.Event()

    # ───────────────────────────────────────────────────────────────
    async def connect(self):
        """Connect to public MQTT broker."""
        try:
            log.info(f"[Bridge] Connecting to MQTT broker {self.broker}:{self.port} as {self.edge_id}...")
            self.client = Client(self.broker, port=self.port, client_id=self.edge_id)
            await self.client.connect()
            self.running = True
            self.connected.set()
            log.info("[Bridge] Connected to broker ✅")
        except MqttError as e:
            log.error(f"[Bridge] Connection failed: {e}")
            self.running = False

    # ───────────────────────────────────────────────────────────────
    async def publish(self, topic, data):
        """Publish message to broker (JSON)."""
        if not self.client:
            log.warning("[Bridge] Publish attempted before connection.")
            return
        try:
            payload = json.dumps({"edge_id": self.edge_id, "topic": topic, "data": data})
            await self.client.publish(f"xsedge/{self.edge_id}/{topic}", payload)
            log.debug(f"[Bridge] Published → xsedge/{self.edge_id}/{topic}")
        except Exception as e:
            log.error(f"[Bridge] Publish failed: {e}")

    # ───────────────────────────────────────────────────────────────
    async def subscribe(self, topic_filter="xsctrl/commands/#", callback=None):
        """Listen for controller commands and forward them via callback."""
        if not self.client:
            log.warning("[Bridge] Subscribe attempted before connection.")
            return

        async with self.client.unfiltered_messages() as messages:
            await self.client.subscribe(topic_filter)
            log.info(f"[Bridge] Subscribed to {topic_filter}")
            async for msg in messages:
                try:
                    payload = json.loads(msg.payload.decode())
                    log.info(f"[Bridge] Received command: {payload}")
                    if callback:
                        await callback(payload)
                except Exception as e:
                    log.error(f"[Bridge] Error handling message: {e}")

    # ───────────────────────────────────────────────────────────────
    async def disconnect(self):
        """Gracefully close connection."""
        try:
            if self.client:
                await self.client.disconnect()
                log.info("[Bridge] Disconnected from broker")
        except Exception as e:
            log.warning(f"[Bridge] Disconnect error: {e}")
        finally:
            self.running = False

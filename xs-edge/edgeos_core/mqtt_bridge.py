import asyncio, json, logging, random, sys
from aiomqtt import Client, MqttError
from edgeos_core.command_handler import CommandHandler
from edgeos_core.rules_sync import RulesSync

log = logging.getLogger("MQTTBridge")

class MQTTBridge:
    """
    MQTT Bridge for XS Edge ↔ Controller communication.
    Works with aiomqtt >=2.4.
    """

    def __init__(self, broker="broker.hivemq.com", port=8000, edge_id=None, rules_engine=None, bus=None):
        self.broker = broker
        self.port = port
        self.edge_id = edge_id or f"xsedge-{random.randint(1000,9999)}"
        self.client = None
        self.running = False
        self.connected = asyncio.Event()
        self.rules_engine = rules_engine      # ✅ fixed name
        self.bus = bus
        self.command_handler = CommandHandler(self.rules_engine)
        self.rules_sync = RulesSync(self.rules_engine, self.bus)

        # ✅ Windows event loop fix
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # ───────────────────────────────────────────────
    async def connect(self):
        """Establish persistent connection to MQTT broker and spawn background listeners."""
        try:
            log.info(f"[Bridge] Connecting to MQTT broker {self.broker}:{self.port} as {self.edge_id}...")
            self.running = True
            self.connected.set()

            # Start listeners in background
            asyncio.create_task(self._listen_for_commands())
            asyncio.create_task(self._listen_for_rules())

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
            async with Client(
                self.broker,
                self.port,
                transport="websockets",
                websocket_path="/mqtt"
            ) as client:
                client._client_id = self.edge_id.encode()
                payload = json.dumps({
                    "edge_id": self.edge_id,
                    "topic": topic,
                    "data": data
                })
                await client.publish(f"xsedge/{self.edge_id}/{topic}", payload.encode())
                log.debug(f"[Bridge] Published → xsedge/{self.edge_id}/{topic}")
        except Exception as e:
            log.error(f"[Bridge] Publish failed: {e}")

    # ───────────────────────────────────────────────
    async def _listen_for_commands(self):
        """Listen for controller → edge commands and dispatch."""
        try:
            async with Client(
                self.broker,
                self.port,
                transport="websockets",
                websocket_path="/mqtt"
            ) as client:
                client._client_id = self.edge_id.encode()
                await client.subscribe(f"xsctrl/commands/{self.edge_id}")
                log.info(f"[Bridge] Subscribed to xsctrl/commands/{self.edge_id}")

                async for msg in client.messages:
                    try:
                        await self.command_handler.handle_command(msg.payload.decode(), self.bus)
                    except Exception as e:
                        log.error(f"[Bridge] Command handling error: {e}")
        except Exception as e:
            log.error(f"[Bridge] Subscribe loop error: {e}")

    # ───────────────────────────────────────────────
    async def _listen_for_rules(self):
        """Listen for controller-pushed rule updates."""
        try:
            async with Client(
                self.broker,
                self.port,
                transport="websockets",
                websocket_path="/mqtt"
            ) as client:
                client._client_id = self.edge_id.encode()
                await client.subscribe(f"xsctrl/rules/{self.edge_id}")
                await client.subscribe("xsctrl/rules/all")
                log.info(f"[Bridge] Subscribed to rule topics for {self.edge_id}")

                async for msg in client.messages:
                    await self.rules_sync.handle_update(msg.payload.decode(), self.edge_id)
        except Exception as e:
            log.error(f"[Bridge] Rule listener error: {e}")

    # ───────────────────────────────────────────────
    async def disconnect(self):
        """Gracefully close connection."""
        try:
            self.running = False
            log.info("[Bridge] Disconnected from broker")
        except Exception as e:
            log.warning(f"[Bridge] Disconnect error: {e}")

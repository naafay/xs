import asyncio, logging, collections, time

log = logging.getLogger("DataBus")

class DataBus:
    """
    Async in-memory message bus with optional persistence and replay buffer.
    Supports publish/subscribe for inter-plugin comms and hooks for controller bridging.
    """

    def __init__(self, db=None, replay_limit=50, enable_persistence=True):
        self.subscribers = {}           # topic → [asyncio.Queue, ...]
        self.replay = {}                # topic → deque of (timestamp, data)
        self.stats = collections.defaultdict(lambda: {"published": 0, "subscribers": 0})
        self.db = db
        self.replay_limit = replay_limit
        self.enable_persistence = enable_persistence
        self.bridge = None              # placeholder for future MQTT/WebSocket bridge

    # ───────────────────────────────────────────────────────────────
    async def publish(self, topic: str, data: dict):
        """
        Publish an event to all subscribers and update replay buffer.
        """
        ts = time.time()
        if topic not in self.replay:
            self.replay[topic] = collections.deque(maxlen=self.replay_limit)
        self.replay[topic].append((ts, data))
        self.stats[topic]["published"] += 1

        # persist to DB (optional)
        if self.db and self.enable_persistence:
            try:
                self.db.insert_event(topic, data)
            except Exception as e:
                log.error(f"[Bus] DB insert error for {topic}: {e}")

        # publish to local subscribers
        if topic in self.subscribers:
            for q in self.subscribers[topic]:
                await q.put(data)
            log.debug(f"[Bus] Published {topic} → {len(self.subscribers[topic])} subs")

        # optional bridge
        if self.bridge:
            try:
                await self.bridge.publish(topic, data)
            except Exception as e:
                log.warning(f"[Bus] Bridge publish failed for {topic}: {e}")

    # ───────────────────────────────────────────────────────────────
    def subscribe(self, topic: str):
        """
        Create a queue and register a subscriber for this topic.
        Returns the asyncio.Queue instance for consumer tasks.
        """
        q = asyncio.Queue()
        self.subscribers.setdefault(topic, []).append(q)
        self.stats[topic]["subscribers"] = len(self.subscribers[topic])
        log.info(f"[Bus] Subscribed → {topic} (total {len(self.subscribers[topic])})")
        return q

    # ───────────────────────────────────────────────────────────────
    def get_stats(self):
        """
        Return current bus statistics and replay buffer sizes.
        """
        report = {}
        for topic, stat in self.stats.items():
            replay_count = len(self.replay.get(topic, []))
            report[topic] = {
                "published": stat["published"],
                "subscribers": stat["subscribers"],
                "replay_depth": replay_count,
            }
        return report

    # ───────────────────────────────────────────────────────────────
    def replay_history(self, topic, limit=10):
        """
        Retrieve last N events for a topic.
        """
        return list(self.replay.get(topic, []))[-limit:]

    # ───────────────────────────────────────────────────────────────
    async def attach_mqtt_bridge(self, bridge):
        """
        Attach external MQTT/WebSocket bridge.
        Bridge must implement async publish(topic, data).
        """
        self.bridge = bridge
        log.info("[Bus] External bridge attached")

    # ───────────────────────────────────────────────────────────────
    def detach_mqtt_bridge(self):
        """Remove the external bridge."""
        self.bridge = None
        log.info("[Bus] External bridge detached")

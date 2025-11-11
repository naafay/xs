import json, logging, os

log = logging.getLogger("RulesSync")

class RulesSync:
    """
    Handles rule update messages received via MQTT.
    Saves rules to config/rules_demo.json and triggers reload.
    """

    def __init__(self, rules_engine, bus):
        self.rules_engine = rules_engine
        self.bus = bus
        self.rules_path = os.path.join("config", "rules_demo.json")

    async def handle_update(self, payload, edge_id):
        """Process incoming rule updates from the Controller."""
        try:
            data = json.loads(payload)

            # Support both formats:
            # 1. {"rules": [...]}
            # 2. [...]
            if isinstance(data, list):
                rules_data = data
            elif isinstance(data, dict) and "rules" in data:
                rules_data = data["rules"]
            else:
                log.warning(f"[RulesSync] Unexpected format: {type(data)}")
                return

            # Write to config file
            os.makedirs(os.path.dirname(self.rules_path), exist_ok=True)
            with open(self.rules_path, "w") as f:
                json.dump(rules_data, f, indent=2)

            # Reload rules into engine
            self.rules_engine.load(self.rules_path)
            log.info(f"[RulesSync] Saved {len(rules_data)} rules to {self.rules_path}")

            # Publish ACK telemetry
            ack_data = {
                "edge_id": edge_id,
                "status": "ack",
                "result": f"{len(rules_data)} rules updated"
            }
            await self.bus.publish(f"ack/rules_update/{edge_id}", ack_data)

        except Exception as e:
            log.error(f"[RulesSync] Error processing rules update: {e}")

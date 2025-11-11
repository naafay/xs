import json, logging, asyncio, os
from pathlib import Path

log = logging.getLogger("CommandHandler")

class CommandHandler:
    def __init__(self, rules):
        self.rules = rules

    async def handle_command(self, payload, bus):
        cmd = json.loads(payload)
        cmd_id = cmd.get("cmd_id")
        edge_id = cmd.get("edge_id")
        action = cmd.get("action")

        result = "unknown"
        try:
            if action == "reload_rules":
                # overwrite rules file if provided
                rules = cmd.get("rules")
                if rules:
                    rules_path = Path("config/rules_demo.json")
                    rules_path.write_text(json.dumps(rules, indent=2))
                self.rules.load()
                result = "Rules reloaded"
            else:
                result = f"Unhandled action: {action}"
        except Exception as e:
            result = f"Error: {e}"

        ack = {"cmd_id": cmd_id, "edge_id": edge_id, "status": "ack", "result": result}
        await bus.publish(f"ack/{cmd_id}", ack)
        log.info(f"[CMD] {edge_id} executed '{action}' → {result}")

import json, logging
log=logging.getLogger("Rules")
class RulesEngine:
    def __init__(self,db): self.db=db; self.rules=[]
    def load(self, path='config/rules_demo.json'):
        try:
            self.rules = json.load(open(path))
            log.info(f"✅ Loaded {len(self.rules)} rules from {path}")
        except Exception as e:
            log.error(f"❌ Failed to load rules from {path}: {e}")
    def evaluate(self, ctx):
        for r in self.rules:
            try:
                # Only evaluate if all variables in the rule exist in ctx
                if all(var in ctx for var in r["if"].replace(">", " ").replace("<", " ").split() if var.isidentifier()):
                    if eval(r["if"], {}, ctx):
                        log.warning(f"Rule {r['name']} triggered")
                        self.db.insert_event(r['name'], ctx)
            except Exception as e:
                log.error(e)
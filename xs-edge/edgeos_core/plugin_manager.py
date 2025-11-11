import importlib.util, yaml, asyncio, logging, hashlib, os
log = logging.getLogger("PluginManager")

class PluginManager:
    def __init__(self, bus, db, rules, sa):
        self.bus, self.db, self.rules, self.sa = bus, db, rules, sa
        self.plugins = {}

    async def load_all(self):
        pdir = os.path.join(os.getcwd(), "plugins")
        for d in os.listdir(pdir):
            if not os.path.isdir(os.path.join(pdir, d)):
                continue
            man = os.path.join(pdir, d, "plugin.yaml")
            if not os.path.exists(man):
                continue
            meta = yaml.safe_load(open(man))
            code = os.path.join(pdir, d, "main.py")
            if self.sa.verify_plugin(code):
                spec = importlib.util.spec_from_file_location(d, code)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                plugin = mod.Plugin(self.bus, self.db, self.rules, meta)
                self.plugins[d] = plugin
                # Launch each plugin in its own async task, supervised
                asyncio.create_task(self.safe_start(plugin))
                log.info(f"Loaded plugin {d}")
            else:
                log.warning(f"SHA mismatch on {d}")

   
    async def safe_start(self, plugin):
        while True:
            try:
                await plugin.on_start()  # if plugin loop crashes, restart
            except Exception as e:
                log.error(f"[{plugin.meta['name']}] crashed: {e}. Restarting in 2s")
                await asyncio.sleep(2)



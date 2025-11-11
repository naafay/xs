import asyncio, random, logging, time

class Plugin:
    def __init__(self, bus, db, rules, meta):
        self.bus = bus
        self.db = db
        self.rules = rules
        self.meta = meta

    async def on_start(self):
        
        while True:
            self.last_heartbeat = time.time()
            try:
                
                links = {
                    "5G": random.randint(40, 120),
                    "VSAT": random.randint(120, 250),
                    "LTE": random.randint(60, 180)
                }
                best = min(links, key=links.get)
                ctx = {"edgelink_best": best, "network_latency": links[best]}
                await self.bus.publish("edgelink/route", ctx)
                try:
                    self.rules.evaluate(ctx)
                except Exception as e:
                    logging.error(f"[{self.meta['name']}] rule eval error: {e}")
                logging.info(f"[EdgeLink] best {best} ({links[best]}ms)")
                await asyncio.sleep(10)
            except Exception as e:
                logging.error(f"[EdgeLink Plugin] crash: {e}")
                await asyncio.sleep(5)

    async def on_stop(self):
        logging.info(f"[{self.meta['name']}] cleaning up resources...")
        # perform cleanup, save state, close sockets, etc.

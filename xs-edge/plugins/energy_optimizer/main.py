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
               
                level = random.randint(20, 100)
                ctx = {"energy_level": level}
                await self.bus.publish("energy/status", ctx)
                try:
                    self.rules.evaluate(ctx)
                except Exception as e:
                    logging.error(f"[{self.meta['name']}] rule eval error: {e}")
                logging.info(f"[Energy] level {level}%")
                await asyncio.sleep(10)
            except Exception as e:
                logging.error(f"[Energy Plugin] crash: {e}")
                await asyncio.sleep(5)

    async def on_stop(self):
        logging.info(f"[{self.meta['name']}] cleaning up resources...")
        # perform cleanup, save state, close sockets, etc.
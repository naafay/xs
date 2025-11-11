import asyncio,random,logging,time
class Plugin:
    def __init__(self,bus,db,rules,meta): self.bus,self.db,self.rules,self.meta=bus,db,rules,meta
    async def on_start(self):
        while True:
            self.last_heartbeat = time.time()
            try:
                latency = random.randint(50, 250)
                ctx = {"network_latency": latency}
                await self.bus.publish("network/metrics", ctx)
                self.rules.evaluate(ctx)
                logging.info(f"[Network] latency {latency} ms")
                await asyncio.sleep(10)
            except Exception as e:
                logging.error(f"Network plugin error: {e}")

    async def on_stop(self):
        logging.info(f"[{self.meta['name']}] cleaning up resources...")
        # perform cleanup, save state, close sockets, etc.
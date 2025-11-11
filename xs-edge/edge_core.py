import asyncio, logging, os, threading, signal, sys, time
from dotenv import load_dotenv
from edgeos_core import data_bus, plugin_manager, rules_engine, local_db, secure_agent, web_api, mqtt_bridge
import uvicorn

# ───────────────────────────────────────────────────────────────
# SETUP
# ───────────────────────────────────────────────────────────────
load_dotenv()
log = logging.getLogger("xs-edge")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logging.getLogger("Rules").setLevel(logging.INFO)
logging.getLogger("PluginManager").setLevel(logging.INFO)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
# ───────────────────────────────────────────────────────────────
# INIT SERVICES
# ───────────────────────────────────────────────────────────────
async def init_services():
    log.info("🚀 Starting XS Edge runtime...")
    db = local_db.DBManager(os.getenv("DB_PATH", "xsedge.db"))
    bus = data_bus.DataBus(db)

    # Optional MQTT bridge setup
    bridge = None
    if os.getenv("MQTT_ENABLED", "false").lower() == "true":
        bridge = mqtt_bridge.MQTTBridge(
            broker=os.getenv("MQTT_BROKER", "test.mosquitto.org"),
            port=int(os.getenv("MQTT_PORT", 1883)),
            edge_id=os.getenv("EDGE_ID", None)
        )
        await bridge.connect()
        await bus.attach_mqtt_bridge(bridge)

    rules = rules_engine.RulesEngine(db)
    rules.load()
    sa = secure_agent.SecureAgent()
    pm = plugin_manager.PluginManager(bus, db, rules, sa)
    await pm.load_all()

    app = web_api.create_app(pm, db, rules, sa, bus)
    return app, pm, db, bridge

# ───────────────────────────────────────────────────────────────
# SHUTDOWN
# ───────────────────────────────────────────────────────────────
async def shutdown(pm, db):
    """Gracefully stop plugins and close DB."""
    log.info("🛑 Initiating graceful shutdown...")

    for name, plugin in pm.plugins.items():
        if hasattr(plugin, "on_stop"):
            try:
                await plugin.on_stop()
                log.info(f"[{name}] stopped cleanly")
            except Exception as e:
                log.error(f"[{name}] error on stop: {e}")

    try:
        db.conn.close()
        log.info("Database connection closed")
    except Exception as e:
        log.error(f"Error closing DB: {e}")

    log.info("✅ XS Edge shutdown complete.")

# ───────────────────────────────────────────────────────────────
# WATCHDOG
# ───────────────────────────────────────────────────────────────
async def watchdog(pm, api_thread, stop_event):
    """Monitor plugin health and restart system if needed."""
    crash_log = {}
    while not stop_event.is_set():
        await asyncio.sleep(10)

        # Check API thread
        if not api_thread.is_alive():
            log.error("💥 API thread stopped — restarting entire XS Edge...")
            os.execv(sys.executable, [sys.executable] + sys.argv)

        # Check plugin registry for stalled tasks
        for name, plugin in pm.plugins.items():
            last_hb = getattr(plugin, "last_heartbeat", None)
            if last_hb and (time.time() - last_hb > 30):
                log.warning(f"⚠️ Plugin {name} unresponsive (>30 s)")
                crash_log.setdefault(name, []).append(time.time())

                # Too many failures → restart entire Edge process
                recent = [t for t in crash_log[name] if time.time() - t < 60]
                if len(recent) >= 3:
                    log.error(f"🔥 {name} failed 3× in 60 s → restarting XS Edge")
                    os.execv(sys.executable, [sys.executable] + sys.argv)

# ───────────────────────────────────────────────────────────────
# MAIN
# ───────────────────────────────────────────────────────────────
async def main():
    app, pm, db, bridge = await init_services()
    port = int(os.getenv("API_PORT", 8000))

    # Start FastAPI (Uvicorn) in background thread
    def run_api():
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")

    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()
    log.info(f"🌐 XS Edge API running on http://0.0.0.0:{port}")

    stop_event = asyncio.Event()

    # Signal handling (cross-platform)
    loop = asyncio.get_running_loop()
    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop_event.set)
    else:
        def win_exit():
            log.info("🧩 Ctrl+C detected — stopping XS Edge...")
            stop_event.set()
        signal.signal(signal.SIGINT, lambda s, f: win_exit())

    # Launch watchdog task
    asyncio.create_task(watchdog(pm, api_thread, stop_event))

    # Keep loop alive
    try:
        while not stop_event.is_set():
            await asyncio.sleep(1)
    finally:
        await shutdown(pm, db)

# ───────────────────────────────────────────────────────────────
# ENTRY POINT
# ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🧩 Manual interrupt received — shutting down...")

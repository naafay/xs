import asyncio, logging, os, sys
from fastapi import FastAPI, WebSocket
from dotenv import load_dotenv
from sqlmodel import SQLModel
from routes import edges, telemetry, commands, auth
from utils.security import SecureAgent
from mqtt_server import MQTTServer
from models import engine
from routes import rules


if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

log = logging.getLogger("XSController")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
load_dotenv()

app = FastAPI(
    title="XS Controller API",
    description="Central orchestrator for XS Edge nodes",
    version="2.0.0"
)

app.include_router(edges.router, prefix="/edges", tags=["Edges"])
app.include_router(telemetry.router, prefix="/telemetry", tags=["Telemetry"])
app.include_router(commands.router, prefix="/commands", tags=["Commands"])
app.include_router(rules.router, prefix="/rules", tags=["Rules"])
app.include_router(auth.router, prefix="/auth", tags=["Auth"])

ws_clients = set()
sa = SecureAgent()
mqtt_server = MQTTServer(broker=os.getenv("MQTT_BROKER", "test.mosquitto.org"), port=int(os.getenv("MQTT_PORT", 1883)))

@app.on_event("startup")
async def startup_event():
    SQLModel.metadata.create_all(engine)
    asyncio.create_task(mqtt_server.listen_and_store(ws_clients))
    log.info("🚀 XS Controller started and MQTT listener running")

@app.websocket("/ws/telemetry")
async def telemetry_ws(ws: WebSocket):
    await ws.accept()
    ws_clients.add(ws)
    try:
        while True:
            await asyncio.sleep(1)
    except Exception:
        pass
    finally:
        ws_clients.remove(ws)
        await ws.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("controller_core:app", host="0.0.0.0", port=int(os.getenv("API_PORT", 9000)), reload=False)

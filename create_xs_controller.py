import os, textwrap

# ────────────────────────────────────────────────
# Helper to create file with content
# ────────────────────────────────────────────────
def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(textwrap.dedent(content).strip() + "\n")

# ────────────────────────────────────────────────
# Base folder
# ────────────────────────────────────────────────
base = "xs-controller"
os.makedirs(base, exist_ok=True)

# ────────────────────────────────────────────────
# controller_core.py
# ────────────────────────────────────────────────
write(f"{base}/controller_core.py", """
import asyncio, logging, os
from fastapi import FastAPI, WebSocket
from dotenv import load_dotenv
from sqlmodel import SQLModel
from routes import edges, telemetry, commands, auth
from utils.security import SecureAgent
from mqtt_server import MQTTServer
from models import engine

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
""")

# ────────────────────────────────────────────────
# mqtt_server.py
# ────────────────────────────────────────────────
write(f"{base}/mqtt_server.py", """
import asyncio, json, logging
from asyncio_mqtt import Client, MqttError
from sqlmodel import Session
from models import Telemetry, engine

log = logging.getLogger("MQTTServer")

class MQTTServer:
    def __init__(self, broker="test.mosquitto.org", port=1883):
        self.broker, self.port = broker, port

    async def listen_and_store(self, ws_clients:set):
        while True:
            try:
                async with Client(self.broker, self.port) as client:
                    await client.subscribe("xsedge/#")
                    log.info(f"[MQTT] Subscribed xsedge/# on {self.broker}")
                    async with client.unfiltered_messages() as messages:
                        async for msg in messages:
                            try:
                                payload = json.loads(msg.payload.decode())
                                edge_id = payload.get("edge_id")
                                data = payload.get("data", {})
                                topic = payload.get("topic")
                                await self._save(edge_id, topic, data)
                                await self._broadcast(ws_clients, payload)
                            except Exception as e:
                                log.error(f"[MQTT] payload error: {e}")
            except MqttError as e:
                log.error(f"[MQTT] broker error {e}, retrying in 5 s")
                await asyncio.sleep(5)

    async def _save(self, edge_id, topic, data):
        with Session(engine) as s:
            rec = Telemetry(edge_id=edge_id, topic=topic, data=json.dumps(data))
            s.add(rec)
            s.commit()

    async def _broadcast(self, ws_clients:set, payload):
        dead = []
        for ws in ws_clients:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for d in dead:
            ws_clients.discard(d)
""")

# ────────────────────────────────────────────────
# models.py
# ────────────────────────────────────────────────
write(f"{base}/models.py", """
import os, datetime, json
from sqlmodel import SQLModel, Field, create_engine

DB_PATH = os.getenv("DB_PATH", "xscontroller.db")
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)

class Edge(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    edge_id: str
    version: str | None = None
    last_seen: datetime.datetime | None = None
    status: str | None = "ONLINE"

class Telemetry(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    edge_id: str
    topic: str
    data: str
    ts: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

    def json_data(self):
        try:
            return json.loads(self.data)
        except Exception:
            return {}
""")

# ────────────────────────────────────────────────
# routes
# ────────────────────────────────────────────────
for name, content in {
    "edges.py": """
from fastapi import APIRouter, HTTPException
from sqlmodel import Session, select
from models import Edge, engine
import datetime, logging
log = logging.getLogger("Edges")

router = APIRouter()

@router.post("/register")
async def register_edge(payload: dict):
    edge_id = payload.get("edge_id")
    version = payload.get("version", "unknown")
    if not edge_id:
        raise HTTPException(400, "edge_id missing")
    with Session(engine) as s:
        edge = s.exec(select(Edge).where(Edge.edge_id == edge_id)).first()
        if not edge:
            edge = Edge(edge_id=edge_id, version=version)
            s.add(edge)
        edge.last_seen = datetime.datetime.utcnow()
        edge.status = "ONLINE"
        s.commit()
    log.info(f"Edge registered: {edge_id}")
    return {"status": "ok", "edge_id": edge_id}

@router.get("/")
async def list_edges():
    with Session(engine) as s:
        return s.exec(select(Edge)).all()
""",
    "telemetry.py": """
from fastapi import APIRouter
from sqlmodel import Session, select
from models import Telemetry, engine

router = APIRouter()

@router.get("/latest")
async def latest(limit:int=20):
    with Session(engine) as s:
        q = select(Telemetry).order_by(Telemetry.id.desc()).limit(limit)
        rows = s.exec(q).all()
        return [{"edge_id":r.edge_id,"topic":r.topic,"data":r.json_data(),"ts":r.ts} for r in rows]
""",
    "commands.py": """
from fastapi import APIRouter
import json, logging
from asyncio_mqtt import Client

router = APIRouter()
log = logging.getLogger("Commands")

@router.post("/send")
async def send_command(payload: dict):
    edge_id = payload.get("edge_id")
    command = payload.get("command")
    if not edge_id or not command:
        return {"error": "missing edge_id or command"}
    async with Client("test.mosquitto.org") as client:
        topic = f"xsctrl/commands/{edge_id}"
        await client.publish(topic, json.dumps(command))
        log.info(f"[CMD] {edge_id} → {command}")
    return {"status": "sent", "topic": topic}
""",
    "auth.py": """
from fastapi import APIRouter, HTTPException
from utils.security import SecureAgent

router = APIRouter()
sa = SecureAgent()

@router.post("/token")
async def issue_token(payload: dict):
    if payload.get("api_key") != sa.master_key:
        raise HTTPException(403, "Invalid API key")
    token = sa.issue_token()
    return {"access_token": token, "token_type": "bearer"}
"""
}.items():
    write(f"{base}/routes/{name}", content)
write(f"{base}/routes/__init__.py", "")

# ────────────────────────────────────────────────
# utils/security.py
# ────────────────────────────────────────────────
write(f"{base}/utils/security.py", """
import jwt, time, os, logging
log = logging.getLogger("Security")

class SecureAgent:
    def __init__(self):
        self.master_key = os.getenv("CTRL_MASTER_KEY", "CtrlMasterKey")
        self.secret = os.getenv("CTRL_JWT_SECRET", "ControllerSecret")

    def issue_token(self):
        payload = {"iat": time.time(), "exp": time.time() + 3600}
        return jwt.encode(payload, self.secret, algorithm="HS256")

    def verify_token(self, token):
        try:
            jwt.decode(token, self.secret, algorithms=["HS256"])
            return True
        except Exception as e:
            log.error(e)
            return False
""")
write(f"{base}/utils/__init__.py", "")

# ────────────────────────────────────────────────
# requirements, Dockerfile, compose, env
# ────────────────────────────────────────────────
write(f"{base}/requirements.txt", """
fastapi>=0.115.0
uvicorn[standard]>=0.31.0
python-dotenv>=1.0.1
sqlmodel>=0.0.22
aiosqlite>=0.20.0
asyncio-mqtt>=0.16.2
paho-mqtt>=2.1.0
pyjwt>=2.9.0
""")

write(f"{base}/Dockerfile", """
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
EXPOSE ${API_PORT}
CMD ["python","controller_core.py"]
""")

write(f"{base}/docker-compose.yml", """
version: "3.9"
services:
  xs-controller:
    build: .
    container_name: xs-controller
    restart: unless-stopped
    env_file: .env
    ports:
      - "${API_PORT}:9000"
    healthcheck:
      test: ["CMD","curl","-f","http://localhost:9000/edges"]
      interval: 30s
      timeout: 5s
      retries: 3
""")

# ────────────────────────────────────────────────
# .env (new!)
# ────────────────────────────────────────────────
write(f"{base}/.env", """
LOG_LEVEL=INFO
API_PORT=9000
DB_PATH=xscontroller.db
MQTT_BROKER=test.mosquitto.org
MQTT_PORT=1883
CTRL_MASTER_KEY=CtrlMasterKey
CTRL_JWT_SECRET=ControllerSecret
""")

print("✅ XS Controller scaffold created successfully in ./xs-controller/")
print("💡 Next steps:")
print("   cd xs-controller")
print("   pip install -r requirements.txt")
print("   python controller_core.py")

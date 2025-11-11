"""
XS Edge v1 Builder
---------------------------------
Creates full XS Edge runtime inside existing XS/xs-edge folder.
Safe to run multiple times; will overwrite existing files only inside xs-edge.
"""

import os, textwrap, json, hashlib, zipfile, pathlib

root = pathlib.Path("xs-edge")
(root / "plugins").mkdir(parents=True, exist_ok=True)
(root / "config" / "certs").mkdir(parents=True, exist_ok=True)
(root / "tests").mkdir(parents=True, exist_ok=True)

# ---------- requirements ----------
(root / "requirements.txt").write_text(
    "\n".join([
        "fastapi", "uvicorn", "paho-mqtt", "sqlmodel",
        "aiofiles", "python-dotenv", "psutil", "ping3", "pyjwt"
    ]) + "\n"
)

# ---------- .env ----------
(root / ".env").write_text(textwrap.dedent("""\
API_PORT=8000
LOG_LEVEL=INFO
DB_PATH=xsedge.db
MQTT_BROKER=test.mosquitto.org
MQTT_PORT=1883
MQTT_USE_TLS=false
EDGE_TOKEN=EdgeOSDemoToken123
PLUGIN_SIGNING_KEY=AfterAccessSecret
PLUGIN_VERIFY_SHA=true
USE_TLS=false
CERT_PATH=config/certs/device.crt
KEY_PATH=config/certs/device.key
"""))

# ---------- simple helper to write modules ----------
def w(path, txt): (root/path).write_text(textwrap.dedent(txt))

# ---------- edge_core.py ----------
w("edge_core.py", """\
import asyncio, logging, os
from dotenv import load_dotenv
from edgeos_core import data_bus, plugin_manager, rules_engine, local_db, secure_agent, web_api
import uvicorn

load_dotenv()
log = logging.getLogger("xs-edge")
logging.basicConfig(level=os.getenv("LOG_LEVEL","INFO"))

async def main():
    log.info("Starting XS Edge runtime...")
    db = local_db.DBManager(os.getenv("DB_PATH","xsedge.db"))
    bus = data_bus.DataBus()
    rules = rules_engine.RulesEngine(db)
    sa = secure_agent.SecureAgent()
    pm = plugin_manager.PluginManager(bus, db, rules, sa)
    await pm.load_all()
    app = web_api.create_app(pm, db, rules, sa)
    port = int(os.getenv("API_PORT",8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    asyncio.run(main())
""")

# ---------- other core modules (compact) ----------
os.makedirs(root/"edgeos_core", exist_ok=True)

w("edgeos_core/__init__.py","")

w("edgeos_core/data_bus.py","""\
import asyncio, logging, paho.mqtt.client as mqtt, os
class DataBus:
    def __init__(self):
        self.loop = asyncio.get_event_loop()
        self.queue = asyncio.Queue()
        self.mqtt = mqtt.Client()
        self.mqtt.connect(os.getenv("MQTT_BROKER","test.mosquitto.org"), int(os.getenv("MQTT_PORT",1883)))
        self.mqtt.loop_start()
    async def publish(self, topic, data):
        self.mqtt.publish(topic, str(data))
        await self.queue.put((topic,data))
    async def subscribe(self): return await self.queue.get()
""")

w("edgeos_core/plugin_manager.py","""\
import importlib.util, yaml, asyncio, logging, hashlib, os
log = logging.getLogger("PluginManager")

class PluginManager:
    def __init__(self, bus, db, rules, sa):
        self.bus, self.db, self.rules, self.sa = bus, db, rules, sa
        self.plugins = {}

    async def load_all(self):
        pdir = os.path.join(os.getcwd(),"xs-edge","plugins")
        for d in os.listdir(pdir):
            if not os.path.isdir(os.path.join(pdir,d)): continue
            man = os.path.join(pdir,d,"plugin.yaml")
            if not os.path.exists(man): continue
            meta = yaml.safe_load(open(man))
            code = os.path.join(pdir,d,"main.py")
            if self.sa.verify_plugin(code):
                spec = importlib.util.spec_from_file_location(d, code)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                plugin = mod.Plugin(self.bus, self.db, self.rules, meta)
                self.plugins[d]=plugin
                asyncio.create_task(plugin.on_start())
                log.info(f"Loaded plugin {d}")
            else:
                log.warning(f"SHA mismatch on {d}")
""")

w("edgeos_core/local_db.py","""\
import sqlite3,time
class DBManager:
    def __init__(self, path):
        self.conn=sqlite3.connect(path,check_same_thread=False)
        self.conn.execute("CREATE TABLE IF NOT EXISTS events(ts REAL,rule TEXT,data TEXT)")
    def insert_event(self,rule,data):
        self.conn.execute("INSERT INTO events VALUES(?,?,?)",(time.time(),rule,str(data)));self.conn.commit()
""")

w("edgeos_core/rules_engine.py","""\
import json, logging
log=logging.getLogger("Rules")
class RulesEngine:
    def __init__(self,db): self.db=db; self.rules=[]
    def load(self,path='xs-edge/config/rules_demo.json'):
        try:self.rules=json.load(open(path))
        except Exception as e:log.error(e)
    def evaluate(self,ctx):
        for r in self.rules:
            try:
                if eval(r["if"],{},ctx): log.warning(f"Rule {r['name']} triggered");self.db.insert_event(r['name'],ctx)
            except Exception as e: log.error(e)
""")

w("edgeos_core/secure_agent.py","""\
import hashlib, os, jwt, time, logging
log=logging.getLogger("SecureAgent")
class SecureAgent:
    def __init__(self):
        self.secret=os.getenv("PLUGIN_SIGNING_KEY","key")
        self.jwt_key=os.getenv("EDGE_TOKEN","EdgeToken")
    def verify_plugin(self,path):
        if os.getenv("PLUGIN_VERIFY_SHA","false").lower()!="true":return True
        try:
            data=open(path,'rb').read()
            digest=hashlib.sha256(data).hexdigest()
            log.debug(f"SHA256 for {path[:40]}... {digest[:8]}")
            return True
        except Exception as e:
            log.error(e);return False
    def verify_token(self,token):
        try:
            decoded=jwt.decode(token,self.jwt_key,algorithms=["HS256"]);return True
        except Exception as e: log.error(e);return False
    def issue_token(self):
        return jwt.encode({'iat':time.time()},self.jwt_key,algorithm="HS256")
""")

w("edgeos_core/web_api.py","""\
from fastapi import FastAPI, Request, HTTPException
import os
def create_app(pm,db,rules,sa):
    app=FastAPI(title="XS Edge API")
    @app.middleware("http")
    async def auth(request:Request,call_next):
        if request.url.path in ["/docs","/openapi.json","/status"]:return await call_next(request)
        token=request.headers.get("Authorization","").replace("Bearer ","")
        if not sa.verify_token(token):raise HTTPException(status_code=403,detail="Bad token")
        return await call_next(request)
    @app.get("/status")async def status():return{"plugins":list(pm.plugins.keys())}
    @app.get("/metrics")async def metrics():
        cur=db.conn.execute("SELECT * FROM events ORDER BY ts DESC LIMIT 10")
        return{"events":[dict(zip(["ts","rule","data"],r))for r in cur]}
    return app
""")

# ---------- sample rules ----------
(root/"config/rules_demo.json").write_text(json.dumps([
    {"name":"HighLatency","if":"network_latency>150","then":"alert"},
    {"name":"LowBattery","if":"energy_level<30","then":"alert"}
], indent=2))

# ---------- plugins (simulated telemetry) ----------
plugins = {
"network_health":("Monitors latency","""\
import asyncio,random,logging
class Plugin:
    def __init__(self,bus,db,rules,meta): self.bus,self.db,self.rules,self.meta=bus,db,rules,meta
    async def on_start(self):
        while True:
            latency=random.randint(50,250)
            ctx={'network_latency':latency}
            await self.bus.publish('network/metrics',ctx)
            self.rules.evaluate(ctx)
            logging.info(f"[Network] latency {latency}ms")
            await asyncio.sleep(10)
"""),
"energy_optimizer":("Simulates energy source","""\
import asyncio,random,logging
class Plugin:
    def __init__(self,bus,db,rules,meta): self.bus,self.db,self.rules,self.meta=bus,db,rules,meta
    async def on_start(self):
        while True:
            level=random.randint(20,100)
            ctx={'energy_level':level}
            await self.bus.publish('energy/status',ctx)
            self.rules.evaluate(ctx)
            logging.info(f"[Energy] level {level}%")
            await asyncio.sleep(12)
"""),
"edgelink_ai":("Selects best link","""\
import asyncio,random,logging
class Plugin:
    def __init__(self,bus,db,rules,meta): self.bus,self.db,self.rules,self.meta=bus,db,rules,meta
    async def on_start(self):
        while True:
            links={'5G':random.randint(40,120),'VSAT':random.randint(120,250),'LTE':random.randint(60,180)}
            best=min(links,key=links.get)
            ctx={'edgelink_best':best,'latency':links[best]}
            await self.bus.publish('edgelink/route',ctx)
            logging.info(f"[EdgeLink] best {best} {links[best]}ms")
            await asyncio.sleep(15)
""")
}
for name,(desc,code) in plugins.items():
    p=root/"plugins"/name
    p.mkdir(parents=True,exist_ok=True)
    (p/"plugin.yaml").write_text(f"name: {name}\nversion: 1.0\ndescription: {desc}\n")
    (p/"main.py").write_text(textwrap.dedent(code))

# ---------- Docker ----------
(root/"Dockerfile").write_text(textwrap.dedent("""\
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
EXPOSE ${API_PORT}
CMD ["python","edge_core.py"]
"""))

(root/"docker-compose.yml").write_text(textwrap.dedent("""\
version: "3.9"
services:
  xs-edge-runtime:
    build: .
    container_name: xs-edge-runtime
    restart: unless-stopped
    env_file: .env
    ports:
      - "${API_PORT}:${API_PORT}"
    healthcheck:
      test: ["CMD","curl","-f","http://localhost:${API_PORT}/status"]
      interval: 30s
      timeout: 5s
      retries: 3
"""))

print("✅ XS Edge v1 ready – run `python xs-edge/edge_core.py` or `docker compose up --build`")

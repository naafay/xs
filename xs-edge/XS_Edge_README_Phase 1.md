# 🧠 XS Edge Runtime
**Version:** 1.0  
**Codename:** “Phase 1 – Core Runtime + Plugin System”

## 🚀 Overview
XS Edge is the local runtime layer of the **EdgeOS** platform — a modular, plugin-driven system designed to operate autonomously at the edge and synchronize intelligently with the **XS Controller** (cloud/core orchestrator) and **XS Hub** (aggregation node).

This component manages:
- Plugin lifecycle & supervision  
- Local rule-based event handling  
- System telemetry & metrics logging  
- Secure API surface (FastAPI + JWT)  
- Optional MQTT bridge to XS Controller

---

## 🧩 Directory Structure
```
XS/
├─ xs-edge/
│  ├─ edge_core.py
│  ├─ .env
│  ├─ config/
│  │   └─ rules_demo.json
│  ├─ edgeos_core/
│  │   ├─ data_bus.py
│  │   ├─ local_db.py
│  │   ├─ plugin_manager.py
│  │   ├─ rules_engine.py
│  │   ├─ secure_agent.py
│  │   ├─ web_api.py
│  │   └─ mqtt_bridge.py
│  ├─ plugins/
│  │   ├─ edgelink_ai/
│  │   ├─ energy_optimizer/
│  │   └─ network_health/
│  └─ requirements.txt
│
├─ xs-controller/
└─ xs-hub/
```

---

## ⚙️ Installation

### 1. Clone & enter the project
```bash
git clone https://github.com/your-org/xs-edge.git
cd xs-edge
```

### 2. Create virtual environment (optional)
```bash
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate # Linux/Mac
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Create a .env file
```env
LOG_LEVEL=INFO
API_PORT=8000
DB_PATH=xsedge.db
MQTT_ENABLED=false
MQTT_BROKER=test.mosquitto.org
MQTT_PORT=1883
EDGE_ID=xs-edge-01
```

---

## 🧱 Run the Runtime
```bash
python -u edge_core.py
```

Expected output:
```
INFO:xs-edge:🚀 Starting XS Edge runtime...
INFO:Rules:✅ Loaded 2 rules from config/rules_demo.json
INFO:PluginManager:Loaded plugin edgelink_ai
🌐 XS Edge API running on http://0.0.0.0:8000
```

---

## 🌐 Endpoints
| Path | Description |
|------|--------------|
| `/status` | Lists active plugins |
| `/health` | JSON system health |
| `/health/view` | HTML dashboard |
| `/metrics` | Recent rule events |
| `/bus/stats` | Data Bus stats |
| `/docs` | Swagger UI |

---

## 🧠 Rules Engine Example
```json
[
  {"name": "HighLatency", "if": "network_latency > 200", "then": "alert"},
  {"name": "LowBattery", "if": "energy_level < 20", "then": "alert"}
]
```

---

## 🔌 Plugin Model
Each plugin has its own `plugin.yaml` and `main.py`.

**plugin.yaml**
```yaml
name: energy_optimizer
version: 1.0
entry: main.py
author: XS Systems
```

**main.py**
```python
import asyncio, random, logging, time

class Plugin:
    def __init__(self, bus, db, rules, meta):
        self.bus = bus
        self.db = db
        self.rules = rules
        self.meta = meta

    async def on_start(self):
        while True:
            ctx = {"energy_level": random.randint(10, 100)}
            await self.bus.publish("energy/status", ctx)
            self.rules.evaluate(ctx)
            await asyncio.sleep(5)
```

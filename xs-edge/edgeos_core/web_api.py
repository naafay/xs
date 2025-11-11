from fastapi import FastAPI, Request, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse, HTMLResponse
import os, time, logging, json

log = logging.getLogger("WebAPI")

def create_app(pm, db, rules, sa, bus):
    """
    XS Edge FastAPI app with REST + HTML dashboard.
    """
    security = HTTPBearer(auto_error=False)
    app = FastAPI(
        title="XS Edge API",
        description="Use the **Authorize** button and paste your token as `Bearer <JWT>` to access protected routes.",
        version="1.0.5",
    )

    # ───────────────────────────────────────────────────────────────
    # AUTH MIDDLEWARE
    # ───────────────────────────────────────────────────────────────
    @app.middleware("http")
    async def auth(request: Request, call_next):
        open_paths = [
            "/docs", "/openapi.json", "/status", "/health",
            "/health/view", "/favicon.ico", "/bus/stats"
        ]
        if request.url.path in open_paths:
            return await call_next(request)

        token_header = request.headers.get("Authorization", "")
        token = token_header.replace("Bearer ", "").strip()
        if not token:
            log.warning(f"Unauthorized access attempt to {request.url.path}")
            return JSONResponse({"detail": "Missing or invalid token"}, status_code=403)

        try:
            if not sa.verify_token(token):
                return JSONResponse({"detail": "Bad token"}, status_code=403)
        except Exception as e:
            log.error(f"Token verification error: {e}")
            return JSONResponse({"detail": "Token verification error"}, status_code=403)

        return await call_next(request)

    # ───────────────────────────────────────────────────────────────
    # PUBLIC ROUTES
    # ───────────────────────────────────────────────────────────────
    @app.get("/status", tags=["default"])
    async def status():
        return {"plugins": list(pm.plugins.keys())}

    start_time = time.time()

    def collect_health():
        """Helper for JSON + HTML health responses."""
        now = time.time()
        plugin_status, degraded = {}, False

        for name, plugin in pm.plugins.items():
            last_hb = getattr(plugin, "last_heartbeat", None)
            if last_hb:
                delta = round(now - last_hb, 1)
                status = "OK" if delta < 30 else "STALE"
                plugin_status[name] = {"last_heartbeat_sec_ago": delta, "status": status}
                if status == "STALE":
                    degraded = True
            else:
                plugin_status[name] = {"status": "NO_HEARTBEAT"}
                degraded = True

        # MQTT bridge info
        mqtt_info = {"enabled": False}
        try:
            bridge = getattr(bus, "bridge", None)
            if bridge:
                mqtt_info = {
                    "enabled": True,
                    "broker": bridge.broker,
                    "port": bridge.port,
                    "edge_id": bridge.edge_id,
                    "connected": getattr(bridge, "running", False),
                }
        except Exception as e:
            mqtt_info = {"enabled": False, "error": str(e)}

        return {
            "system": "XS Edge",
            "version": "1.0.0",
            "uptime_sec": round(now - start_time, 1),
            "overall_status": "OK" if not degraded else "DEGRADED",
            "plugins": plugin_status,
            "mqtt_bridge": mqtt_info,
        }

    # JSON health (for controller use)
    @app.get("/health", tags=["default"])
    async def health():
        return JSONResponse(collect_health())

    # HTML view (for humans)
    @app.get("/health/view", tags=["dashboard"])
    async def health_view():
        data = collect_health()
        plugins_html = "".join(
            f"<tr><td>{name}</td><td>{p.get('status')}</td>"
            f"<td>{p.get('last_heartbeat_sec_ago','-')}</td></tr>"
            for name, p in data["plugins"].items()
        )
        mqtt = data["mqtt_bridge"]
        mqtt_status = (
            f"{'🟢' if mqtt.get('connected') else '🔴'} {mqtt.get('broker')}:{mqtt.get('port')}"
            if mqtt.get('enabled') else "Disabled"
        )

        html = f"""
        <html>
        <head>
            <title>XS Edge Health Dashboard</title>
            <meta http-equiv="refresh" content="10">
            <style>
                body {{ font-family: 'Segoe UI', sans-serif; background:#101010; color:#EEE; }}
                h2 {{ color:#ffd700; }}
                table {{ border-collapse: collapse; width: 80%; margin:auto; }}
                td,th {{ border:1px solid #444; padding:6px; text-align:center; }}
                th {{ background:#333; }}
                tr:nth-child(even){{ background:#1a1a1a; }}
                .ok {{ color:#00ff99; }}
                .stale {{ color:#ffaa00; }}
                .bad {{ color:#ff5555; }}
            </style>
        </head>
        <body>
            <h2 align="center">XS Edge Health Dashboard</h2>
            <p align="center">Auto-refresh every 10s | Version {data['version']}</p>
            <table>
                <tr><th>Plugin</th><th>Status</th><th>Last Heartbeat (s)</th></tr>
                {plugins_html}
            </table>
            <br>
            <table>
                <tr><th>System</th><td>{data['system']}</td></tr>
                <tr><th>Overall</th><td>{data['overall_status']}</td></tr>
                <tr><th>Uptime (s)</th><td>{data['uptime_sec']}</td></tr>
                <tr><th>MQTT Bridge</th><td>{mqtt_status}</td></tr>
            </table>
            <p align="center" style="font-size:12px;">Last updated: {time.strftime('%H:%M:%S')}</p>
        </body>
        </html>
        """
        return HTMLResponse(content=html)

    # Bus stats
    @app.get("/bus/stats", tags=["default"])
    async def bus_stats():
        return bus.get_stats()

    # ───────────────────────────────────────────────────────────────
    # PROTECTED ROUTES
    # ───────────────────────────────────────────────────────────────
    @app.get("/metrics", tags=["default"])
    async def metrics(credentials: HTTPAuthorizationCredentials = Security(security)):
        cur = db.conn.execute("SELECT * FROM events ORDER BY ts DESC LIMIT 10")
        events = [dict(zip(["ts", "rule", "data"], r)) for r in cur]
        return {"events": events}

    return app

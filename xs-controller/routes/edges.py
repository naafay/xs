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

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

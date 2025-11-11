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

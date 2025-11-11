from sqlmodel import SQLModel, Field, Column, JSON
from typing import Optional, Dict
import datetime
from models import engine

class CommandLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    cmd_id: str
    edge_id: str
    command: Dict = Field(sa_column=Column(JSON))
    status: str = "SENT"
    result: Optional[str] = None
    ts_sent: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    ts_ack: Optional[datetime.datetime] = None

class Ruleset(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    edge_id: str
    rules: Dict = Field(sa_column=Column(JSON))
    ts_uploaded: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

def init_extra_tables():
    SQLModel.metadata.create_all(engine)

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

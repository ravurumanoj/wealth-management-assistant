from datetime import datetime, timedelta
from jose import jwt, JWTError
from fastapi import HTTPException, Header
from dotenv import load_dotenv
import os

load_dotenv()

MCP_SECRET_KEY = str(os.getenv("MCP_SECRET_KEY"))

ALGORITHM = "HS256"

def create_access_token(username: str, secret: str):
    if secret.lower() == MCP_SECRET_KEY.lower():
        payload = {
            "sub": username,
            "exp": datetime.utcnow() + timedelta(hours=1)
        }

        return jwt.encode(
            payload,
            MCP_SECRET_KEY,
            algorithm=ALGORITHM
        )
    else:
        raise HTTPException(status_code=401, detail="Invalid MCP Secret Key")


def verify_mcp_token(authorization: str = Header(None)):

    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization Header"
        )

    try:
        token = authorization.replace("Bearer ", "")

        payload = jwt.decode(
            token,
            MCP_SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        return payload

    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Invalid Token"
        )
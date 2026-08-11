from datetime import datetime, timedelta
from jose import jwt, JWTError
from fastapi import HTTPException, Header
from dotenv import load_dotenv
import os

load_dotenv()

SECRET_KEY = str(os.getenv("JWT_SECRET_KEY"))
ALGORITHM = "HS256"

def create_access_token(username: str):

    payload = {
        "sub": username,
        "exp": datetime.utcnow() + timedelta(hours=1)
    }

    return jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )


def verify_token(authorization: str = Header(None)):

    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization Header"
        )

    try:

        token = authorization.replace(
            "Bearer ",
            ""
        )

        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        return payload

    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Invalid Token"
        )
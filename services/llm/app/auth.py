"""JWT auth shared with auth-service via HS256 secret (JWKS lands with Kong JWT)."""

import os
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt

bearer = HTTPBearer(auto_error=False)
SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")


def current_user(creds: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    if not creds:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing token")
    try:
        payload = jwt.decode(creds.credentials, SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token")
    return {"id": str(payload.get("sub")), "role": str(payload.get("role"))}

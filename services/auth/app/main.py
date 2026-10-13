import os
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest
from sqlalchemy.orm import Session
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[2] / "common"))
from consul import register_with_consul
from .db import Base, engine, get_db
from .models import User
from .schemas import LoginIn, RegisterIn, TokenOut, UserOut
from .security import create_tokens, decode_token, hash_password, verify_password
from .deps import get_current_user, redis_client

PORT = int(os.getenv("PORT", "8001"))
SERVICE_NAME = os.getenv("SERVICE_NAME", "auth-service")
REQUESTS = Counter("http_requests_total", "total requests", ["service", "path"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    register_with_consul(SERVICE_NAME, PORT)
    yield


app = FastAPI(title=SERVICE_NAME, lifespan=lifespan)


@app.get("/health")
def health():
    return {"service": SERVICE_NAME, "status": "ok"}


@app.get("/api/v1/auth/health")
def auth_health():
    REQUESTS.labels(SERVICE_NAME, "/api/v1/auth/health").inc()
    return {"service": SERVICE_NAME, "status": "ok"}


@app.post("/api/v1/auth/register", response_model=UserOut, status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if body.role not in ("candidate", "recruiter"):
        raise HTTPException(status_code=422, detail="role must be candidate|recruiter")
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=409, detail="email exists")
    user = User(email=body.email, password_hash=hash_password(body.password), role=body.role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserOut(id=user.id, email=user.email, role=user.role)


@app.post("/api/v1/auth/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="bad credentials")
    access, refresh = create_tokens(user.id, user.role)
    return TokenOut(access_token=access, refresh_token=refresh)


@app.post("/api/v1/auth/refresh", response_model=TokenOut)
def refresh(body: dict, db: Session = Depends(get_db)):
    try:
        payload = decode_token(body.get("refresh_token", ""))
    except Exception:
        raise HTTPException(status_code=401, detail="invalid refresh")
    user = db.get(User, payload.get("sub"))
    if not user:
        raise HTTPException(status_code=401, detail="unknown user")
    access, refresh_tok = create_tokens(user.id, user.role)
    return TokenOut(access_token=access, refresh_token=refresh_tok)


@app.post("/api/v1/auth/logout", status_code=204)
def logout(body: dict):
    try:
        redis_client().sadd("jwt_blacklist", body.get("access_token", ""))
    except Exception:
        pass
    return Response(status_code=204)


@app.get("/api/v1/auth/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return UserOut(id=user.id, email=user.email, role=user.role)


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

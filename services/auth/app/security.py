import os
from datetime import datetime, timedelta, timezone
from jose import jwt
from passlib.context import CryptContext

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
JWT_ALG = "HS256"
ACCESS_MIN = int(os.getenv("JWT_ACCESS_MIN", "30"))
REFRESH_DAYS = int(os.getenv("JWT_REFRESH_DAYS", "7"))


def hash_password(pw: str) -> str:
    return pwd_ctx.hash(pw)


def verify_password(pw: str, hashed: str) -> bool:
    return pwd_ctx.verify(pw, hashed)


def _encode(sub: str, role: str, minutes: int = 30, days: int = 0) -> str:
    exp = datetime.now(timezone.utc) + (timedelta(days=days) if days else timedelta(minutes=minutes))
    return jwt.encode({"sub": sub, "role": role, "exp": exp}, JWT_SECRET, algorithm=JWT_ALG)


def create_tokens(user_id: str, role: str) -> tuple[str, str]:
    return _encode(user_id, role, minutes=ACCESS_MIN), _encode(user_id, role, days=REFRESH_DAYS)


def decode_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])

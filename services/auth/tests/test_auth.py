import os

os.environ["DATABASE_URL"] = "sqlite:///./test_auth.db"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["JWT_SECRET"] = "test-secret"

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

import app.main as auth_main
from app.db import Base, get_db
from app.security import hash_password, verify_password

# Neutralize lifespan side effects (real postgres + consul) for unit tests.
auth_main.register_with_consul = lambda *a, **k: None
Base.metadata.create_all = (lambda *a, **k: None)  # noqa: E731

test_engine = create_engine(
    "sqlite:///./test_auth.db",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
# Create tables on the sqlite engine directly via the Table objects.
Base.metadata.tables["users"].create(bind=test_engine, checkfirst=True)


class FakeRedis:
    def __init__(self):
        self.sets = {}

    def sadd(self, key, *vals):
        self.sets.setdefault(key, set()).update(vals)
        return 1

    def sismember(self, key, val):
        return val in self.sets.get(key, set())


fake_redis = FakeRedis()
auth_main.redis_client = lambda: fake_redis
import app.deps as auth_deps
auth_deps.redis_client = lambda: fake_redis


def override_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


auth_main.app.dependency_overrides[get_db] = override_db

client = TestClient(auth_main.app)

EMAIL = "cycle1@example.com"
PW = "password123"


def setup_module():
    # Clean slate per file run.
    with TestingSession() as db:
        db.execute(Base.metadata.tables["users"].delete())
        db.commit()
    fake_redis.sets.clear()


def test_security_hash_roundtrip():
    h = hash_password("somepassword1")
    assert verify_password("somepassword1", h) is True
    assert verify_password("wrongpassword", h) is False


def test_register_ok():
    r = client.post("/api/v1/auth/register", json={"email": EMAIL, "password": PW, "role": "candidate"})
    assert r.status_code == 201, r.text
    assert r.json()["email"] == EMAIL


def test_register_duplicate_409():
    r = client.post("/api/v1/auth/register", json={"email": EMAIL, "password": PW, "role": "candidate"})
    assert r.status_code == 409


def test_register_bad_role_422():
    r = client.post("/api/v1/auth/register", json={"email": "other@example.com", "password": PW, "role": "admin"})
    assert r.status_code == 422


def test_health():
    assert client.get("/health").status_code == 200
    assert client.get("/api/v1/auth/health").status_code == 200


def _login():
    r = client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PW})
    assert r.status_code == 200, r.text
    return r.json()


def test_login_bad_password_401():
    r = client.post("/api/v1/auth/login", json={"email": EMAIL, "password": "wrongpassword9"})
    assert r.status_code == 401


def test_me_ok():
    toks = _login()
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {toks['access_token']}"})
    assert r.status_code == 200
    assert r.json()["email"] == EMAIL


def test_me_no_token_401():
    assert client.get("/api/v1/auth/me").status_code == 401


def test_refresh_ok():
    toks = _login()
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": toks["refresh_token"]})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_refresh_invalid_401():
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": "junk"}).status_code == 401


def test_logout_revokes_token():
    toks = _login()
    r = client.post("/api/v1/auth/logout", json={"access_token": toks["access_token"]})
    assert r.status_code == 204
    r2 = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {toks['access_token']}"})
    assert r2.status_code == 401


def teardown_module():
    try:
        os.remove("test_auth.db")
    except OSError:
        pass

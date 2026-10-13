# HireFit — Async Resume Parser + Semantic Job Matcher

Cycle 0 scope: monorepo layout, local infra via Compose, gateway + discovery stubs.

## Run (Cycle 0)
```powershell
docker compose up --build
# consul UI: http://localhost:8500
# kong admin: http://localhost:8001
# auth health via gateway: http://localhost:8000/api/v1/auth/health
```

See `gateway/kong.yml` for routes, `docker-compose.yml` for services.

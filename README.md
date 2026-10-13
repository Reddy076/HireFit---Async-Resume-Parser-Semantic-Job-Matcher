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

## Cycle 1 - Auth + Upload
- `POST /api/v1/auth/register {email,password,role}` -> 201
- `POST /api/v1/auth/login` -> {access_token, refresh_token}
- `GET /api/v1/auth/me` with `Authorization: Bearer <access>`
- `POST /api/v1/resumes/upload` (multipart PDF, <=10MB) -> 202 {resume_id, status: queued}
- `GET /api/v1/resumes/{id}` -> metadata + status
- Events: `resume.uploaded` to Kafka (logs if broker down), files to MinIO bucket `resumes`.

## Cycle 2 - Parsing worker
- `parsing-service:8003` consumes `resume.uploaded`, extracts text with PyMuPDF, splits sections (header/experience/skills/education/projects/certifications/summary), PATCHes `resume-service`, emits `resume.parsed`.
- Scanned PDFs (no text layer) are marked `needs_ocr`; OCR lands in a later cycle.
- `GET /api/v1/resumes/{id}` now returns `status`, `has_parsed`, `parsed`.
- Existing DBs auto-upgrade via `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`.

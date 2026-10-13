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
- Events: `resume.uploaded` to Kafka (logs if broker down), files to LocalStack S3 bucket `resumes`.

## Cycle 2 - Parsing worker
- `parsing-service:8003` consumes `resume.uploaded`, extracts text with PyMuPDF, splits sections (header/experience/skills/education/projects/certifications/summary), PATCHes `resume-service`, emits `resume.parsed`.
- Scanned PDFs (no text layer) are marked `needs_ocr`; OCR lands in a later cycle.
- `GET /api/v1/resumes/{id}` now returns `status`, `has_parsed`, `parsed`.
- Existing DBs auto-upgrade via `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`.

## Cycle 3 - Job service
- `job-service:8004` CRUD: `POST/GET /api/v1/jobs`, `GET/PATCH/DELETE /api/v1/jobs/{id}`.
- Writes are recruiter-only with owner check; reads need any valid JWT (shared HS256 secret with auth-service; JWKS lands with Kong JWT plugin later).
- Create emits `job.created`; Kong routes `/api/v1/jobs`.

## Cycle 4 - Embedding + vector search
- `embedding-service:8005`: chunking (120-word windows), `POST /api/v1/embeddings/resumes/{id}`, `/jobs/{id}`, `/search`.
- Backends: `hash` default (dependency-free, 768d) and `st` (all-mpnet-base-v2 via requirements-ml.txt, Docker only, falls back to hash). Switching backends needs re-index.
- Worker auto-indexes on `resume.parsed` + `job.created`. Vectors stored as JSON; pgvector ANN index is a later-cycle perf follow-up.

## Cycle 5 - Matching orchestrator
- `matching-service:8006`: `POST /api/v1/match/single {resume_id, job_id}`, `POST /api/v1/match/job/{job_id} {top_k, limit}`, `GET /api/v1/match/resume/{rid}/job/{jid}`.
- Score = 0.7*rerank + 0.3*skill-overlap, persisted in `matches` (unique per resume+job, idempotent re-run).
- Rerank backends: `heuristic` default, `ce` (ms-marco-MiniLM, Docker only, falls back). Bulk flow: embedding search → per-resume rerank → ranked store.

## Cycle 6 - RAG explainer
- `llm-service:8007`: `POST /api/v1/explain {resume_id, job_id, kind}` with kinds `explain` (fit + [section] citations), `gaps` (2-week plan per missing skill), `rewrite` (tailored bullets). `GET /api/v1/explain/logs` history.
- Backends: `heuristic` default (template over real scores, offline), `ollama` (any model via OLLAMA_HOST, falls back to heuristic). Every generation logged with prompt + context sections.

## Cycle 7 - Frontend
- Next.js 14 (`web/`, served on :3000 via compose): landing with live service status, login/register with role routing.
- Candidate: PDF upload → status polling → parsed section viewer → single match with score bar + skill gaps → explain/gaps/rewrite tabs.
- Recruiter: job post + list, per-job bulk rank table with CSV export.

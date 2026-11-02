# ExamFlow — Full-stack online examination platform

A deployable starter platform built with Next.js + TypeScript and FastAPI. It includes authentication, student self-registration, one-time Admin bootstrap, permission-grant scaffolding for moderators, exam creation APIs, question management APIs, live exam state controls, answer persistence, automatic objective scoring, leaderboard publication, and a reviewed PDF-to-exam import workflow that extracts subject, chapter, set, duration, question text and MCQ options using Bengali/English OCR.

> This is a functional MVP foundation, not a fully audited high-stakes examination product. Read **Known limitations** before using it for a real exam.

## Stack

- Frontend: Next.js 15, React 19, TypeScript, Tailwind CSS
- Backend: FastAPI, Pydantic, SQLAlchemy 2, Alembic
- Database: PostgreSQL (SQLite can be used for local smoke tests)
- PDF extraction: PyMuPDF + Tesseract OCR (`ben` + `eng`) + Pytesseract
- Deployment: Docker; frontend can deploy to Vercel and API to a Python container host

## Run locally with Docker

1. Copy `backend/.env.example` to `backend/.env` and set a strong `SECRET_KEY`.
2. From this directory run:

   ```bash
   docker compose up --build
   ```

3. Open `http://localhost:3000` for the website and `http://localhost:8000/docs` for the API docs.
4. Create the first Admin from the backend container:

   ```bash
   docker compose exec api python -m app.seed_admin
   ```

   The Admin bootstrap is deliberately a one-time CLI action; do not expose a public admin-creation endpoint in production.

## Run without Docker

### Backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
# Linux: install the Bengali and English OCR language packs
sudo apt-get install -y tesseract-ocr tesseract-ocr-ben tesseract-ocr-eng
cp .env.example .env
# Set DATABASE_URL and SECRET_KEY in .env
alembic upgrade head
python -m app.seed_admin
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Set `NEXT_PUBLIC_API_URL=/api/v1` and `API_INTERNAL_URL=http://localhost:8000` if you want Next.js to proxy API requests. For local frontend dev, add the backend origin to `FRONTEND_ORIGINS` if calling the API directly.

## Production deployment

### Recommended low-cost topology

- Frontend: Vercel (Next.js)
- Backend: a Python container host that supports persistent FastAPI processes
- Database: managed PostgreSQL free tier initially
- Files: object storage only when needed; avoid storing uploaded PDFs in the app container filesystem

Configure the frontend environment:

- `NEXT_PUBLIC_SITE_URL=https://your-domain.example`
- `NEXT_PUBLIC_API_URL=/api/v1`
- `API_INTERNAL_URL=https://your-api-host.example`

`API_INTERNAL_URL` is used by Next.js rewrites to proxy `/api/v1/*` to FastAPI. This keeps browser requests same-origin and allows the API's HttpOnly cookie to be set on the frontend domain. If you deploy frontend and API on different origins without the proxy, configure cookie SameSite/Secure and CSRF protection correctly before production.

Configure the backend environment:

- `ENVIRONMENT=production`
- `DATABASE_URL=postgresql+psycopg://...`
- `SECRET_KEY=<long-random-secret>`
- `FRONTEND_ORIGINS=https://your-domain.example`
- `COOKIE_SECURE=true`
- `MAX_UPLOAD_MB=15`

Run database migrations before serving traffic:

```bash
alembic upgrade head
```

Start the API with:

```bash
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

Create the initial Admin once using `python -m app.seed_admin` in the backend deployment shell. Disable shell access or protect deployment credentials after setup.

### Free-tier and data-traffic strategy

1. Keep PostgreSQL as the source of truth; do not store exam answers in browser storage only.
2. Paginate lists and cap API responses. The starter endpoints currently cap common lists at 100–500 rows; add cursor pagination before growing beyond that.
3. Send answer writes only when a student changes an answer. Do not poll the server every second for the countdown.
4. Use the server's start timestamp and local countdown display. Synchronize on page load, reconnect and state changes.
5. Avoid large dashboard chart libraries and large images. The public landing page uses CSS/SVG-like primitives and no external stock images.
6. Compress responses at the hosting proxy/CDN and enable immutable caching for Next static assets.
7. Store PDFs only when necessary, enforce upload limits and delete temporary files after review.
8. Run OCR only when an Admin explicitly uploads a PDF. The current import runs synchronously with page/file limits; move large-document OCR into Celery workers before scaling import volume.
9. Keep database connection pools small on free tiers. Tune pool size to the provider's connection limit.
10. Export and back up data regularly. Free database plans may sleep, expire, cap storage, or delete inactive projects.

## First Admin and role model

- Student registration is public and always creates `student` accounts.
- Admin accounts are created only through the CLI bootstrap command.
- Exactly-one-Admin is enforced by the bootstrap check in this starter; for a strict production guarantee, add a PostgreSQL partial unique index migration on `users` where `role = 'admin'`.
- Moderators are created by the Admin. Permissions are stored as individual permission grants.
- The backend checks permissions on protected routes. Add permission checks to every new management endpoint.

## Main API routes

All routes are under `/api/v1`.

| Area | Routes |
|---|---|
| Health | `GET /health` |
| Auth | `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me` |
| Users | `GET /users`, `POST /admin/moderators` |
| Moderator permissions | `PUT /moderators/{id}/permissions` |
| Exams | `POST /exams`, `GET /exams`, `GET /exams/{id}`, `POST /exams/{id}/publish` |
| Live controls | `POST /exams/{id}/control/start|pause|resume|end` |
| Questions | `POST /exams/{id}/questions`, `GET /exams/{id}/questions`, `GET /exams/{id}/questions/manage`, `PATCH /exams/{id}/questions/{question_id}` |
| Access | `POST /exams/{id}/access` |
| Attempts | `POST /exams/{id}/attempts`, `GET /attempts/{id}`, `PUT /attempts/{id}/answers/{question_id}`, `POST /attempts/{id}/submit` |
| Results | `POST /exams/{id}/publish-results`, `GET /exams/{id}/leaderboard` |
| PDF question preview | `POST /imports/pdf/preview` |
| Create exam from reviewed PDF | `POST /imports/pdf/create-exam` |
| Legacy PDF text preview | `POST /imports/pdf` |

Interactive API docs are available at `/docs` outside production mode.

## PDF-to-exam workflow

Open **Dashboard → Import PDF** and upload a question paper. The API:

1. Reads PDF text with PyMuPDF. Bengali PDFs and image-only/scanned PDFs are rendered page-by-page and processed with Tesseract `ben+eng`; this handles legacy Bangla font encodings and scanned documents.
2. Detects subject/paper, chapter, exam title, set, declared question count and duration from the header.
3. Segments numbered question blocks and extracts A/B/C/D options into structured question records.
4. Shows an editable preview. Admins/moderators can correct metadata, question text, options, type, marks, answer keys, and exclude questions. Saved exams also have an Edit questions page from the dashboard.
5. Creates a draft examination and questions only after the user approves the preview.

**Important limitations:** OCR is not perfect. Mathematical notation, vector symbols, superscripts, dense tables and diagrams may be misread. The supplied 7-page sample was tested: all 100 numbered question blocks were detected. In that test, 85 questions had four options detected, 12 had three, one had two, and two had no options detected; these flagged items need correction in the review screen. Mathematical notation and some Bengali glyphs also need human checking. Correct answers are not inferred. The reviewer can enter correct options/accepted answers during import or later from **Dashboard → Edit questions**. Publishing is blocked until every question has a valid answer key.

The backend Docker image installs Tesseract and Bengali/English language data. For a non-Docker Linux deployment, install `tesseract-ocr`, `tesseract-ocr-ben` and `tesseract-ocr-eng` before starting FastAPI.

## SEO and privacy

- Public landing page has title/description/Open Graph metadata.
- `robots.ts` and `sitemap.ts` are generated by Next.js.
- Login, registration, dashboard and exam-taking routes are noindex/disallowed from crawling.
- Do not expose private exam questions, answer keys, student records or result pages to search engines.
- Public exam discovery pages can be added later with curated metadata and only public exam information.

## Important limitations before real deployment

The current MVP intentionally keeps dependencies and resource usage low. Before using it for consequential/high-stakes exams, implement and test:

- Full immutable exam-version snapshots and per-attempt question snapshots (the current schema has a simplified question model).
- Server-authoritative pause-aware deadline calculations. The starter pause/resume control updates state but its attempt deadline handling needs a dedicated timer service before production.
- WebSocket event fan-out using Redis for multiple API instances; live events are not yet wired into the API.
- Autosave retry queue, idempotency keys and optimistic concurrency for answer writes.
- Correct partial-credit/negative-marking policy and manual short-answer grading workflow.
- AI-based extraction of complex diagrams/equations, asynchronous Celery processing for large PDFs, and secure object storage. Current OCR runs synchronously with upload limits and requires manual review.
- CSRF protection, email verification, password reset, rate limiting, brute-force protection and security headers at the API edge.
- Complete moderator permission enforcement for every admin action, student management and audit logs.
- Full automated tests, load testing at 500 concurrent users and database backup/restore drills.
- Public result release policy and leaderboard privacy review.

Do not assume the project is suitable for 500 concurrent users until a realistic load test passes on the actual hosting/database plan.

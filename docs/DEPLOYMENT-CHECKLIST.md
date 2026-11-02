# Production deployment checklist

- [ ] Use a managed PostgreSQL database with automated backups.
- [ ] Set a unique random SECRET_KEY; never commit secrets.
- [ ] Set ENVIRONMENT=production and COOKIE_SECURE=true.
- [ ] Set exact FRONTEND_ORIGINS; do not use wildcard origins with cookies.
- [ ] Configure Next.js API rewrite to the backend origin.
- [ ] Run `alembic upgrade head` before starting API instances.
- [ ] Create exactly one Admin from the backend CLI.
- [ ] Disable public docs in production (already configured).
- [ ] Configure rate limits at reverse proxy/API gateway.
- [ ] Configure email verification and password recovery before public launch.
- [ ] Confirm backend image includes Tesseract and `ben`/`eng` language data for PDF OCR.
- [ ] Configure durable object storage for uploaded files.
- [ ] Configure error monitoring without logging passwords/tokens/answers.
- [ ] Test database restore from backup.
- [ ] Load test concurrent exam start and answer-save bursts.
- [ ] Test pause/resume, time expiry, duplicate submit and network reconnect.
- [ ] Review leaderboard disclosure and student privacy.


## New owner-content and scheduling migration

- Ensure the deployed API image contains migration `0003_owner_content_schedule`.
- Deploy the backend so `alembic upgrade head` adds the `site_content` table and exam schedule/time-extension columns.
- Sign in as the Admin and open `/dashboard/site-content` to review the public owner profile and homepage copy.
- Open an upcoming exam's `Schedule & timing` page and verify the displayed time zone before saving a schedule.
- For a live exam, test a small time extension and confirm a student client receives the updated remaining time on its next 15-second synchronization.

## Neon + Cloudinary profile-photo deployment (v1.2.0)

- [ ] Rotate any credentials that were previously shared in an `.env` file.
- [ ] Create Neon PostgreSQL and use its pooled connection string for `DATABASE_URL`.
- [ ] Confirm `DATABASE_URL` is PostgreSQL SSL (`sslmode=require`); the app normalizes `postgresql://` to `postgresql+psycopg://`.
- [ ] Keep `DB_POOL_SIZE=2` and `DB_MAX_OVERFLOW=1` for the free-tier connection budget.
- [ ] Add Cloudinary cloud name, API key and API secret to the FastAPI service only.
- [ ] Set `CLOUDINARY_FOLDER=examflow` and `MAX_UPLOAD_BYTES=307200`.
- [ ] Set `CORS_ORIGINS` to the exact Vercel origin and `COOKIE_SECURE=true`.
- [ ] Confirm the Render health check responds at `/api/v1/health`.
- [ ] Confirm Alembic migration `0004_user_avatars_cloudinary` is applied.
- [ ] Test user profile upload with a JPG/PNG/WebP file below 300 KiB and confirm a file above the limit is rejected.
- [ ] Test Admin-only owner portrait upload from Dashboard → Manage website.
- [ ] Confirm Cloudinary API secret is not present in frontend variables or client bundles.

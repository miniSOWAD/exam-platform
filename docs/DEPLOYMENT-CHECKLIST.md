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

# Deploy ExamFlow with Neon, Render and Cloudinary

This project uses Neon PostgreSQL for relational data, Render (or another Docker-capable Python host) for FastAPI, Vercel for Next.js, and Cloudinary for profile photographs.

## 1. Rotate previously shared credentials

The `.env` uploaded during project setup contained credentials. Treat them as exposed and rotate the Neon database password, Cloudinary API secret, JWT secret, Gmail app password and any administrator password that was present. Do not put production `.env` files in the ZIP or source control.

## 2. Create Neon PostgreSQL database

1. Create a Neon project and database.
2. In the Neon dashboard, copy the **pooled** connection string (the hostname usually contains `-pooler`).
3. Convert the URL scheme from `postgresql://` to `postgresql+psycopg://` when entering it into `DATABASE_URL`. The backend also normalizes a plain `postgresql://` URL automatically.
4. Keep the SSL query parameters, such as `sslmode=require` and `channel_binding=require`, supplied by Neon.

Example shape only (replace every placeholder):

```text
postgresql+psycopg://DB_USER:DB_PASSWORD@YOUR-NEON-ENDPOINT-pooler.REGION.aws.neon.tech/DB_NAME?sslmode=require&channel_binding=require
```

The default SQLAlchemy pool is intentionally small (`DB_POOL_SIZE=2`, `DB_MAX_OVERFLOW=1`) to reduce Neon connection usage. If you reuse the previous project `.env`, values such as `DB_POOL_SIZE=5` and `DB_MAX_OVERFLOW=10` are clamped to 2 and 1. A legacy `MAX_UPLOAD_BYTES=5242880` is also clamped to 307,200 bytes. Do not raise the database pool without checking the plan's connection limit.

## 3. Create Cloudinary credentials

1. Create or open a Cloudinary account.
2. From the Cloudinary dashboard, copy Cloud name, API Key and API Secret.
3. Add them as server-side backend environment variables only.
4. Set `CLOUDINARY_FOLDER=examflow`.

The API accepts only JPG/JPEG, PNG and WebP images. The server checks the actual decoded image format and enforces a hard maximum of 307,200 bytes (300 KiB). SVG and animated image uploads are not accepted. The original is stored in Cloudinary; delivery URLs use a 512x512 crop with `f_auto,q_auto:eco` optimization.

User profile photo routes:

- `POST /api/v1/users/me/avatar` — authenticated student, moderator or admin uploads their own photo (`multipart/form-data`, field `file`).
- `DELETE /api/v1/users/me/avatar` — removes their own photo.
- `POST /api/v1/site/content/owner-avatar` — Admin-only upload for the permanent site-owner photo.

The database stores only the Cloudinary delivery URL and public ID, not image bytes. Users cannot change another user's photo through these routes.

## 4. Deploy FastAPI to Render

The repository includes `render.yaml`. Create a Render Blueprint or Docker Web Service from the repository root. Set these environment variables in the Render service:

| Variable | Value |
|---|---|
| `APP_ENV` | `production` |
| `DATABASE_URL` | Neon pooled connection string using `postgresql+psycopg://` |
| `JWT_SECRET` | Use the generated value from the included Render Blueprint, or set a new long random secret manually |
| `CORS_ORIGINS` | Exact deployed frontend origin, e.g. `https://your-app.vercel.app` |
| `COOKIE_SECURE` | `true` |
| `DB_POOL_SIZE` | `2` |
| `DB_MAX_OVERFLOW` | `1` |
| `CLOUDINARY_CLOUD_NAME` | Cloudinary cloud name |
| `CLOUDINARY_API_KEY` | Cloudinary API key |
| `CLOUDINARY_API_SECRET` | Cloudinary API secret |
| `CLOUDINARY_FOLDER` | `examflow` |
| `MAX_UPLOAD_BYTES` | `307200` |
| `ALLOWED_IMAGE_TYPES` | `image/jpeg,image/png,image/webp,image/jpg` |

The backend settings accept the previous project variable names (`APP_ENV`, `JWT_SECRET`, `CORS_ORIGINS`, `ACCESS_TOKEN_MINUTES`, and `CLOUDINARY_*`). The old project's SMTP/OTP variables are ignored because those email/OTP workflows are not part of this ExamFlow build. The Docker startup command runs `alembic upgrade head` before launching Uvicorn. The health endpoint is `/api/v1/health`. The container listens on Render's `$PORT`.

After the service is healthy, open a Render shell and create the first Admin:

```bash
python -m app.seed_admin
```

You can set `ADMIN_EMAIL`, `ADMIN_NAME` and `ADMIN_PASSWORD` as secret environment variables to avoid interactive prompts. Use a unique password, then remove `ADMIN_PASSWORD` from the service environment after creating the account.

## 5. Deploy Next.js to Vercel

Set the frontend root directory to `frontend`. Configure:

```text
NEXT_PUBLIC_SITE_URL=https://YOUR-FRONTEND-DOMAIN
NEXT_PUBLIC_API_URL=/api/v1
API_INTERNAL_URL=https://YOUR-RENDER-API-DOMAIN
```

`API_INTERNAL_URL` is a server-side value. The Next.js rewrite proxies `/api/v1/*` to FastAPI so browser requests can use the frontend origin and the HttpOnly authentication cookie. Set `CORS_ORIGINS` on Render to the exact frontend origin, including scheme and no trailing slash.

## 6. Local Docker setup

```bash
cp backend/.env.example backend/.env
```

For local Docker, leave the sample local database URL in place. Add your Cloudinary values and a new local JWT secret, then run:

```bash
docker compose up --build
```

To use Neon from local Docker, replace `DATABASE_URL` in `backend/.env` with your Neon pooled connection string. The Compose file still starts its local PostgreSQL container, but the API will use the `DATABASE_URL` from `backend/.env`; this is useful for testing against Neon, though the local `db` container is then unused.

## 7. Free-tier and traffic notes

- Profile image uploads are limited to 300 KiB before they are sent to Cloudinary.
- Image bytes are not stored in Neon; only URL/public ID strings are stored.
- The browser loads transformed 512px images, not original uploads.
- Use the Neon pooled connection URL and keep the small SQLAlchemy pool.
- Free plans have independent storage, compute, bandwidth and inactivity quotas; monitor both Neon and Cloudinary usage.
- Never include Cloudinary API secrets or Neon credentials in frontend variables prefixed with `NEXT_PUBLIC_`.

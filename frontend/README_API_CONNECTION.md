# ExamFlow frontend API connection and authentication

The browser must call the same-origin API prefix:

```env
NEXT_PUBLIC_API_URL=/api/v1
```

Next.js proxies `/api/v1/*` to FastAPI on the server. The default upstream is:

```env
API_INTERNAL_URL=https://examflow-api.fastapicloud.dev
```

For local backend development, set `API_INTERNAL_URL=http://localhost:8000`. Set this server-only variable in the frontend deployment environment before building/redeploying. If it is omitted, the known ExamFlow FastAPI Cloud origin is used automatically. A trailing slash or an accidental `/api/v1` suffix is normalized.

**Do not set `NEXT_PUBLIC_API_URL` to the external FastAPI URL.** The access token is an HttpOnly `SameSite=Lax` cookie. Calling FastAPI directly from a different browser origin prevents that cookie from being sent reliably and makes valid users appear signed out. Keep `NEXT_PUBLIC_API_URL=/api/v1` so login, `/auth/me`, dashboard, and leaderboard requests all use the same frontend origin.


## Database-backed API errors

The dashboard requests `/api/v1/exams` after confirming the signed-in user. A backend HTTP 500 is not treated as a logout. If it occurs after an Admin Control Center deployment, check the FastAPI startup logs for Alembic migration output. The backend now applies pending migrations at startup by default (`AUTO_MIGRATE=true`) before serving the dashboard. The frontend also displays plain-text API error bodies instead of replacing every response with a generic status message.

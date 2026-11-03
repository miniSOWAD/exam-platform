# ExamFlow frontend API connection

The browser should call the same-origin API prefix:

```env
NEXT_PUBLIC_API_URL=/api/v1
```

Next.js forwards `/api/v1/*` to the FastAPI service using the server-only variable:

```env
API_INTERNAL_URL=https://examflow-api.fastapicloud.dev
```

Set `API_INTERNAL_URL` in `frontend/.env.local` for local development and in Vercel Project Settings → Environment Variables for deployment. Use only the origin: do not append `/api/v1`. A trailing slash is now normalized automatically.

After changing this value, restart `npm run dev` locally or redeploy the Vercel project so the rewrite is rebuilt. Keep `NEXT_PUBLIC_API_URL=/api/v1`; do not expose Cloudinary or database secrets to the browser.

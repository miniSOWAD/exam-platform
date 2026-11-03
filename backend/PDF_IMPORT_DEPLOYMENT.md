# ExamFlow PDF import on FastAPI Cloud

## What was fixed

- Added `MAX_PDF_UPLOAD_MB` (default 15 MB). This is separate from `MAX_UPLOAD_BYTES=307200`, which is only for profile photos.
- The previous preview endpoint referenced `settings.max_upload_mb`, a setting that did not exist and caused an internal-server-error response before parsing started.
- Text-based Bengali PDFs now use their embedded text layer when it contains recognizable question blocks. OCR is no longer forced on every Bengali PDF.
- OCR work runs in a worker thread so a multi-page PDF does not block FastAPI's async event loop.
- The parser uses local Tesseract when the executable and both `ben` and `eng` language packs are available.
- FastAPI Cloud's standard Python dependency build does not install OS packages such as the Tesseract executable. For scanned PDFs on FastAPI Cloud, an optional OCR.Space fallback is supported.

## FastAPI Cloud environment variables

Set these in the ExamFlow app's Environment Variables page:

```env
MAX_PDF_UPLOAD_MB=15
MAX_PDF_PAGES=30
PDF_OCR_DPI=240
```

For digitally generated PDFs with usable text layers, no third-party OCR key is required.

For scanned PDFs or legacy Bengali-font PDFs whose embedded text cannot be parsed, optionally create an OCR.Space API key and add it as an encrypted secret:

```env
OCR_SPACE_API_KEY=your_ocr_space_api_key
OCR_SPACE_ENGINE=3
OCR_SPACE_TIMEOUT_SECONDS=90
```

OCR.Space Engine 3 supports Bengali through automatic language detection. When the key is configured, only PDFs that need OCR are sent to OCR.Space. If you do not want question papers sent to a third-party OCR provider, leave the key empty and run the backend in a Docker/container environment with `tesseract-ocr`, `tesseract-ocr-ben`, and `tesseract-ocr-eng` installed. See the OCR.Space API documentation before enabling it: https://ocr.space/ocrapi

## Redeploy backend

From the `backend` directory on Windows:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -c "from app.main import app; print(app.title)"
fastapi deploy
```

After deployment, test:

- `GET https://YOUR-API.fastapicloud.dev/api/v1/health`
- `POST https://YOUR-API.fastapicloud.dev/api/v1/imports/pdf/preview` (authenticated multipart form field `file`)

## Frontend API proxy

Set `API_INTERNAL_URL` to the FastAPI Cloud origin only, e.g. `https://examflow-api.fastapicloud.dev` (no trailing slash and no `/api/v1`). `NEXT_PUBLIC_API_URL` should remain `/api/v1` so browser requests go through the Next.js same-origin rewrite and retain the HttpOnly auth cookie flow.

After changing `API_INTERNAL_URL`, restart `next dev` locally or redeploy the frontend so Next.js rebuilds its rewrite configuration.

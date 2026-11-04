# ExamFlow PDF import deployment notes

## Native-text PDFs

The preview endpoint now checks the PDF's embedded text layer first. Digitally generated Bengali/English PDFs with recognizable question blocks are parsed locally; they do not require Tesseract or OCR.Space. The parser filters repeated headers/footers, detects text columns when possible, and supports Bengali option labels in parenthesized, one-per-line, and inline forms.

## Scanned or damaged-text PDFs

Image-only PDFs and PDFs with unusable embedded text require OCR. FastAPI Cloud's standard source build may not include the Tesseract executable or Bengali language data. For these files, configure the following environment variables in FastAPI Cloud:

```env
MAX_PDF_UPLOAD_MB=15
OCR_SPACE_API_KEY=YOUR_OCR_SPACE_API_KEY
OCR_SPACE_ENGINE=3
OCR_SPACE_TIMEOUT_SECONDS=90
```

Set the key as an encrypted secret, then redeploy. If Tesseract with both `ben` and `eng` is installed, it is preferred. Otherwise, OCR.Space is used only when the embedded text is not structurally usable.

OCR.Space receives rasterized page images. Do not enable remote OCR for confidential question papers unless your document policy allows the provider to process page images.

## Frontend API proxy

Keep this browser setting:

```env
NEXT_PUBLIC_API_URL=/api/v1
```

Set the server-side backend origin only (no path suffix):

```env
API_INTERNAL_URL=https://examflow-api.fastapicloud.dev
```

The Next.js rewrite removes trailing slashes automatically. Restart `npm run dev` after changing environment variables, or redeploy the frontend.

## Verification after deployment

1. Open `https://examflow-api.fastapicloud.dev/api/v1/health` and confirm the service reports `ok`.
2. Sign in to ExamFlow and upload the searchable Biology test PDF.
3. Confirm the preview reports `Embedded text extracted`, 50 questions, and four options per question.
4. Upload a scanned PDF only after confirming that a Bengali OCR engine is configured.

## Preview endpoint status codes

- `400`: unreadable or password-protected PDF.
- `413`: PDF exceeds the configured upload-size limit.
- `415`: file is not a PDF.
- `422`: FastAPI request validation failed before extraction.
- `502`: OCR provider request failed or rejected the document.
- `503`: no Bengali-capable OCR engine is configured for a scanned/damaged-text PDF.
- `500`: unexpected internal extraction failure; inspect backend logs for the traceback.

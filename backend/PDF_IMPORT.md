# ExamFlow Bengali PDF import

## PDF preview behaviour

- The parser first reads a PDF's embedded text layer. Digitally generated Bengali/English PDFs with recognizable question blocks are parsed locally without an external OCR call.
- Native text is accepted only when question blocks and option coverage are sufficiently complete. If the embedded text is damaged or absent, the parser falls back to local Tesseract (`ben+eng`) or OCR.Space.
- Page headers and footers are excluded from question parsing. Unruled two-column text layouts are detected from text-block positions when possible.
- Bengali option labels `ক.`, `খ.`, `গ.`, `ঘ.`, their parenthesized forms, and common English A-D labels are supported, including multiple options on one line.
- Correct answers are never inferred.

## FastAPI Cloud setup

FastAPI Cloud's standard source build may not include the Tesseract executable or Bengali language data. For scanned/image-only PDFs, configure these app environment variables:

```env
OCR_SPACE_API_KEY=YOUR_OCR_SPACE_API_KEY
OCR_SPACE_ENGINE=3
OCR_SPACE_TIMEOUT_SECONDS=90
MAX_PDF_UPLOAD_MB=15
```

Set the API key as an encrypted secret, then redeploy. If local Tesseract with both `ben` and `eng` is available, it is preferred. Otherwise, OCR.Space is used only when the PDF has no usable embedded text layer.

OCR.Space receives rasterized page images. Do not enable remote OCR for confidential question papers unless your document policy allows that provider to process page images.

## Local setup

- Install Tesseract OCR plus Bengali (`ben`) and English (`eng`) language data, or configure `OCR_SPACE_API_KEY` in `backend/.env` for image-only PDFs.
- Install Python dependencies: `python -m pip install -r requirements.txt`.
- `MAX_UPLOAD_BYTES=307200` is only for profile photos. PDF uploads use the separate `MAX_PDF_UPLOAD_MB` setting.

## API status codes

- `400`: unreadable or password-protected PDF.
- `413`: PDF exceeds the upload-size limit.
- `415`: file is not a PDF.
- `422`: request validation failed before extraction (for example, a missing multipart `file` field).
- `502`: OCR provider request failed or rejected the document.
- `503`: no Bengali-capable OCR engine is configured for an image-only/damaged-text PDF.
- `500`: unexpected internal extraction failure; inspect backend logs for the traceback.

## Frontend proxy

Keep `NEXT_PUBLIC_API_URL=/api/v1`. Set `API_INTERNAL_URL` to the FastAPI origin only, for example `https://examflow-api.fastapicloud.dev`, with no trailing slash and no `/api/v1` suffix. Next.js also strips accidental trailing slashes before creating the rewrite.

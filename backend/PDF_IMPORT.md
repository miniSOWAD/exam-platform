# ExamFlow Bengali PDF import

## What changed in v1.3.0

- Uses page layout to split two-column question papers before OCR.
- Reads the first-page heading separately to detect subject, chapter, exam title, set, and declared question count.
- Supports Bengali question numbers and Bengali option labels `(ক)`, `(খ)`, `(গ)`, `(ঘ)`.
- Supports option markers that OCR commonly confuses, including `€ক)`, `খে)`, `(A)`, `(1)`, and `(*)`.
- Handles question numbers that OCR places on a separate line.
- Runs alternate Tesseract page-segmentation passes only when a question block is incomplete.
- Never guesses correct answers.

## FastAPI Cloud setup

FastAPI Cloud's source build does not automatically install the Tesseract OS executable or Bengali language data. Configure these app environment variables for Bengali/scanned PDFs:

```env
OCR_SPACE_API_KEY=YOUR_OCR_SPACE_API_KEY
OCR_SPACE_ENGINE=3
OCR_SPACE_TIMEOUT_SECONDS=90
MAX_PDF_UPLOAD_MB=15
```

Set the API key as a secret, then redeploy the app. The backend will prefer local Tesseract when it detects the executable and both `ben` and `eng` language packs; otherwise it uses OCR.Space Engine 3.

OCR.Space receives rasterized page images for OCR. Do not enable the remote fallback for confidential question papers unless your document policy allows that provider to process the page images.

## Local setup

- Install Tesseract OCR plus Bengali (`ben`) and English (`eng`) language data, or configure `OCR_SPACE_API_KEY` in `backend/.env`.
- Install Python dependencies: `python -m pip install -r requirements.txt`.
- Keep `MAX_UPLOAD_BYTES=307200` for profile photos. PDF uploads use the separate `MAX_PDF_UPLOAD_MB` setting.

## Deploy

From the `backend` directory:

```powershell
fastapi deploy
```

After deployment, verify `GET /api/v1/health`, then upload the supplied Bengali sample PDF through the ExamFlow PDF Exam Builder.

# Architecture notes

## Request flow
Browser -> Next.js UI -> same-origin `/api/v1` rewrite -> FastAPI -> SQLAlchemy -> PostgreSQL.

## Trust boundaries
The backend is authoritative for role checks, exam status, answer persistence, scoring and result publication. The frontend may improve UX but must never be trusted to determine marks or permissions.

## Low-traffic defaults
- Server components for public static pages.
- Small client components only for interactive forms and exam controls.
- No polling-based countdown; calculate display time locally and sync at lifecycle events.
- Paginated/capped list responses.
- No third-party analytics or external image dependencies by default.
- Compress and cache static assets at the CDN.

## Data model direction
Question bank records should eventually be immutable revisions. Each published exam version should reference exact question revisions. Each attempt should snapshot the exact questions/marks/options shown to that student. This is required to preserve historical scoring after edits.


## PDF import pipeline

`POST /api/v1/imports/pdf/preview` uses PyMuPDF to inspect the PDF. When Bengali glyphs are present or the PDF has no usable text layer, pages are rendered at 240 DPI and passed through local Tesseract `ben+eng` OCR to avoid broken Unicode mappings from legacy Bengali fonts. The parser identifies header metadata and question blocks, then emits editable question/option objects. `POST /api/v1/imports/pdf/create-exam` stores the approved exam metadata and question rows. Answer keys are deliberately left empty unless an answer key is explicitly supplied and reviewed.

OCR is synchronous in this MVP and limited to 15 MB / 30 pages. Large-volume production imports should move into Celery workers and object storage.

The PDF review screen supports manual answer-key entry (`selected_option_ids`, `value`, or `accepted_answers`). The dashboard question editor can correct imported question content and keys before the first attempt. Publishing validates that every question has a usable answer key; answer keys are never exposed by student-facing question responses.

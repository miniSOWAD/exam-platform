# Changelog

## 1.1.0 — Owner profile and exam schedule controls

- Replaced the homepage's user-specific left rail with the permanent public site-owner profile for Md Mahruf Alam.
- Added an Admin-only website content manager for branding, homepage copy, owner profile, contact/social links, subjects, section copy, feature cards and footer text.
- Added a top-right account/profile menu for authenticated students, moderators and Admins.
- Added public discovery for exams configured for all students.
- Added exam schedule start/end fields, schedule editing and an early-start guard.
- Added upcoming/live/paused exam duration extension.
- Added server-computed remaining-time responses and 15-second client timer synchronization so live extensions reach students.
- Added Alembic migration `0003_owner_content_schedule` and updated deployment documentation.


## 1.2.0 — Cloudinary profiles and Neon deployment

- Added authenticated profile-photo upload and removal for students, moderators and Admins.
- Enforced a server-side 300 KiB limit and JPG/PNG/WebP content validation.
- Added Cloudinary storage and optimized 512px delivery URLs; no image binaries are stored in PostgreSQL.
- Added Admin-only Cloudinary upload for the permanent site-owner portrait.
- Added user avatar URL to auth responses and the top-right account control.
- Added a personal profile page.
- Added Neon-compatible PostgreSQL URL normalization and low-connection pooling.
- Added Render Blueprint settings and Neon/Cloudinary deployment instructions.
- Added Alembic migration 0004 for user avatar references.

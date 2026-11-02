# ExamFlow frontend and owner-profile update

The public homepage follows the supplied academic portfolio reference: warm ivory surfaces, pale mint and blue panels, muted teal details, editorial serif headings, subtle grid texture, rounded cards and restrained motion.

## Homepage layout

- **Left owner rail:** Always displays the public site owner's profile, defaulting to **Md Mahruf Alam — Site Owner · Tutor & Examiner**. It never displays the signed-in student's identity. The Admin can edit the owner name, designation, biography, education, institution, expertise, profile image URL, contact details and social links through `/dashboard/site-content`.
- **Center hero:** Its eyebrow, title, highlighted title, description, CTA labels and supported subjects are loaded from the public `site_content` record.
- **Right exam panel:** Guests see public (`all_students`) published/live/paused exams and are asked to sign in before participating. Authenticated users see the exams they are allowed to access.
- **Calendar:** Uses real `scheduled_start_at` values returned by the public exam endpoint to mark exam days in the current month. It does not invent university exam dates.
- **Leaderboard:** Loads published exam rankings for signed-in users and permits switching between result-published exams.
- **Feature section and footer:** Section headings, descriptions, feature-card content and footer text are admin-editable.

## User account control

When signed in, the top-right navigation replaces Sign in/Get started with the user's initials and account menu. The menu links to that user's dashboard and sign-out action. Admins also get a direct link to the website content manager. The user account remains separate from the public owner profile.

## Admin-managed website content

Open **Dashboard → Manage website** (`/dashboard/site-content`). The Admin can edit site branding, top ribbon, homepage hero, CTA labels, owner profile, subject labels, upcoming-exam/calendar/leaderboard/feature section headings and descriptions, add/remove feature cards, social links and footer copy. The owner image is currently entered as a publicly reachable image URL; direct file upload/storage is not part of this release.

## Exam schedule and time control

Every non-student exam card links to **Schedule & timing** (`/dashboard/exams/{id}/schedule`). Draft and upcoming/published exams can have their start and optional end date/time set or changed. An Admin cannot manually start a scheduled exam before its scheduled start. Authorized staff can add minutes to upcoming, live or paused exams. The API increases `duration_seconds` and, when present, `scheduled_end_at`. Students fetch the server-computed remaining time at attempt start and synchronize every 15 seconds while the attempt is open, so a live extension is reflected on the next sync.

## Data and traffic behavior

- The root layout server-fetches site content through `API_INTERNAL_URL` with a 60-second revalidation window, so the customized owner profile and public copy are present in the initial HTML for SEO. A single shared client context supplies the Header, homepage and Footer; it avoids duplicate content requests. If `API_INTERNAL_URL` is not configured, the provider falls back to one client-side content request.
- Leaderboard data is requested only when a signed-in user has a published-results exam selected.
- No polling loop, third-party chart library, stock image or autoplay media is used on the landing page.
- The owner photo is a single configured image URL; no additional remote asset requests are made by the CSS-only hero illustration.

## SEO and privacy

The homepage keeps semantic headings and Next.js metadata. The document title, description, Open Graph title and subject keywords are derived from the Admin-managed brand name, hero description and subject list. `API_INTERNAL_URL` enables the root layout to server-fetch the public site content (60-second cache) so customized copy is in the initial HTML. Private dashboard and examination routes remain excluded from indexing. Public exam discovery returns only `all_students` exams in published/live/paused states; private selected-student exams and answer keys are not exposed by this endpoint.

## Current integration boundaries

- Owner profile photos use a public image URL. A secure upload-to-object-storage feature can be added later.
- Exam schedules are set by Admin/authorized moderators. The Admin manually starts an exam; scheduled start is an early-start guard, not an automatic scheduler.
- Live duration extensions are reflected through server timer synchronization every 15 seconds. Redis WebSocket fan-out and automatic forced submission at a deadline remain separate production-hardening tasks.

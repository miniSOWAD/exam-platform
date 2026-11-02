# ExamFlow frontend redesign

The public homepage now follows the supplied academic portfolio reference: warm ivory surfaces, pale mint and blue panels, muted teal details, editorial serif headings, subtle grid texture, rounded cards and restrained motion.

## Homepage layout

- **Left profile rail:** Shows the signed-in user's name, role and email from `GET /api/v1/auth/me`. Guests see a sign-in prompt. The current backend user model does not include a profile-image field, so the avatar uses the user's initials rather than pretending an uploaded photo exists.
- **Center hero:** Introduces ExamFlow and names Mathematics, Physics, Chemistry and Biology as supported study areas.
- **Right exam panel:** For signed-in users, loads exams from `GET /api/v1/exams`, prioritizes live exams, and shows published exams as upcoming. Guests are prompted to sign in. A published exam is not shown as immediately startable because the backend only permits attempts after an Admin starts it.
- **Calendar:** Displays the current month and today's date. The current backend `Exam` model has no scheduled-start field, so the UI explicitly indicates that actual university exam dates are not yet available rather than inventing schedule entries.
- **Leaderboard:** Loads the first available published examination from `GET /api/v1/exams/{id}/leaderboard`; users can switch between published examinations. The API remains authenticated.
- **Feature section:** Explains exam creation, live controls and performance reporting.

## Data and traffic behavior

- The homepage makes one authentication request and, only for signed-in users, one exam-list request.
- A leaderboard request is made only when at least one result-published exam exists; changing the selected exam fetches only that leaderboard.
- No polling loop, third-party image, charting library or autoplay media was added.
- The hero artwork is CSS-only, so it adds no external image request.
- Existing backend endpoints, PDF import flow, dashboard actions and examination routes are unchanged.

## SEO

The homepage remains server-rendered through Next.js with static semantic copy and metadata. Public subject and feature descriptions are crawlable. Authenticated exam data is hydrated client-side and is not exposed as public SEO content. Existing `robots.ts`, `sitemap.ts`, and noindex metadata for private routes remain in place.

## Known UI integration boundaries

- Profile photos cannot be displayed until a profile-image field and upload/storage API are added.
- Calendar event markers cannot be populated until the backend supports scheduled exam dates and returns them in the exam API.
- The public landing page does not expose private exam titles, student data, scores or answer keys to crawlers.

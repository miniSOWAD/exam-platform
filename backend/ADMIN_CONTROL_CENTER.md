# ExamFlow Admin Control Center

This update adds an administrator-only sidebar and three management areas while retaining the existing dashboard and website editor.

## Admin navigation

- **Admin workspace** — existing examination workspace, with an absolute duration editor on each exam card.
- **User management** — Student and Moderator tabs; create accounts, block/unblock, promote/demote, and permanently remove non-admin accounts.
- **Leaderboard management** — By Exam, By Paper, and By Subject; add manual records, review automatically calculated rankings, and remove manual or automatic entries from a selected leaderboard.
- **Manage website** — existing site-content editor.
- **Sign out** — signs out from the admin sidebar.

The sidebar is shown only to accounts whose authenticated role is `admin`. Existing student and moderator dashboard layouts are retained.

## Backend API additions

All admin routes require an authenticated administrator. The API checks the role server-side; hiding the controls in the browser is not the security boundary.

### User management

- `GET /api/v1/admin/users?role=student|moderator&search=&include_inactive=true`
- `POST /api/v1/admin/users`
- `PATCH /api/v1/admin/users/{user_id}/status`
- `PATCH /api/v1/admin/users/{user_id}/role`
- `DELETE /api/v1/admin/users/{user_id}`

Removal deletes the user account, their personal attempts and user-linked access/leaderboard records. Exams and site records created or updated by that account are reassigned to the current administrator so they are not lost. Administrator accounts cannot be removed or demoted through these endpoints.

Newly created/promoted moderators have no permissions by default. The admin must grant only the permissions they need through the existing moderator-permission workflow.

### Examination duration

- `PATCH /api/v1/exams/{exam_id}/duration`
- Body: `{"duration_minutes": 75}`

This sets the total duration, rather than only adding time. It is available to admins for draft, published, live and paused exams. It supports increases and reductions while an exam is running. The response reports how many in-progress attempts are now out of time. The client should warn the administrator before a live reduction; the server recalculates remaining time using the updated total duration.

The older `POST /api/v1/exams/{exam_id}/extend-time` endpoint remains available for compatibility.

### Leaderboard management

- `GET /api/v1/admin/leaderboards?scope=exam&exam_id=...`
- `GET /api/v1/admin/leaderboards?scope=paper&paper=1st%20Paper&subject=Biology`
- `GET /api/v1/admin/leaderboards?scope=subject&subject=Biology`
- `POST /api/v1/admin/leaderboards/entries`
- `POST /api/v1/admin/leaderboards/remove`

Scope values are `exam`, `paper`, and `subject`. Exam rankings use the best submitted attempt per student for that exam. Paper and subject rankings aggregate each student's best submitted attempt per matching exam. Accuracy is calculated as correct answers divided by the total questions in those attempts; unanswered questions therefore do not inflate accuracy. Scores are summed for paper/subject aggregates.

Manual entries can include an optional student email/profile/username identifier. The API links the record to an existing student when the identifier matches their email, full name, or profile ID; otherwise it retains the supplied identifier as display metadata. `max_score` is optional and enables score-ratio accuracy for a manual-only entry. If the maximum is omitted, manual accuracy is shown as unavailable.

An administrator can remove a manual-only entry or exclude a registered student from a particular leaderboard without deleting the student's exam attempts. Exclusions are scoped to the selected exam, paper (and optional subject), or subject. Adding the student back manually clears the matching exclusion.

The public per-exam leaderboard now includes score and accuracy and combines manual exam entries with submitted student attempts after results are published.

## Paper metadata

`exams.paper` is optional and accepts `1st Paper` or `2nd Paper`. It is available in the manual exam form and PDF-import exam metadata. For older exams without explicit metadata, paper ranking infers the paper from common English and Bengali labels in the exam title, subject, chapter, or set name (for example `1st Paper`, `First Paper`, `প্রথম পত্র`, `২য় পত্র`). If an older exam title does not identify its paper, it will not contribute to automatic paper rankings until its paper metadata is set in a future metadata editor.

## Database migration

The migration `0005_admin_control_center` merges the two existing migration heads and adds:

- `exams.paper`
- `leaderboard_entries`
- `leaderboard_exclusions`

The FastAPI application lifespan now runs `alembic upgrade head` before accepting requests. This is important for FastAPI Cloud deployments that launch `app.main:app` directly and may not execute the Dockerfile command. `AUTO_MIGRATE=true` is the default. Set `AUTO_MIGRATE=false` only if a separate deployment job applies migrations before application startup.

PostgreSQL startup migrations use a transaction-scoped advisory lock so multiple application instances do not race to apply the same migration. If a migration fails, application startup fails visibly instead of serving database-backed routes that return HTTP 500. Existing exam and attempt records are preserved by the additive migrations.

## Verification

The backend regression suite includes user lifecycle, live duration increase/decrease, attempt-derived exam/paper/subject rankings, manual ranking, and leaderboard removal tests. The migration was applied to a fresh SQLite database successfully. Frontend TSX syntax and targeted TypeScript checks were run. A full Next.js production build was not possible in this environment because package installation could not reach the npm registry.

The configured FastAPI Cloud host could not be resolved from this environment, so live cloud API/authenticated deployment verification remains outstanding. Do not interpret local tests as proof that the cloud deployment has already been updated.

# Administrator exam mode

## What changed
- Admins can open any non-archived exam through `POST /api/v1/exams/{exam_id}/admin-attempts`.
- Admin attempt questions include `answer_key`; normal student attempt questions never include it.
- Admin attempts are stored with `is_admin_attempt=true`, can be saved outside live status for review/preview, and are excluded from student leaderboard aggregation.
- The admin attempt uses the existing answer-saving/evaluation format. Per-attempt pause baselines preserve remaining time correctly across repeated pauses and reschedules.
- The admin exam page has a fixed bottom control dock: start now, pause, resume, stop, update total duration, and change schedule.
- Admin can reschedule a live/paused exam. A future time pauses the exam and sets `scheduled_resume_at`; subsequent exam detail/list/attempt polling automatically resumes it at the due time while preserving paused seconds.
- Published exams with a future `scheduled_start_at` automatically become live when an exam list/detail/join request observes that the time has arrived.

## Migration
Deploy the backend and run `alembic upgrade head`. Migration `0006_admin_exam_mode` adds `attempts.is_admin_attempt` and `exams.scheduled_resume_at`. It uses the existing `attempts.pause_seconds_at_start` column from migration `0004_attempt_pause_baseline` to preserve per-attempt timer accounting.

## Security
Only `Role.admin` can create admin attempts, receive answer keys in attempt payloads, force-start, and reschedule live exams. Student APIs do not expose correct answers. Admin attempts are not included in student leaderboard calculations.

## Restarting an ended examination

The site administrator can restart an `ended` or `results_published` examination. Use `POST /exams/{exam_id}/control/force-start` for an immediate new run, or `PATCH /exams/{exam_id}/schedule` with a future `scheduled_start_at` to schedule a new run. Sending `scheduled_start_at: null` starts immediately. This is admin-only. A new `run_number` is created, previous attempts are retained, and student attempt limits apply separately to each run. See `ADMIN_ENDED_EXAM_RESTART.md`.

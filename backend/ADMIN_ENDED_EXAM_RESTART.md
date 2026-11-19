# Administrator restart of ended exams

See the project-level `README_ADMIN_ENDED_EXAM_RESTART.md` for the full behavior and deployment guide.

The site administrator may reschedule exams in `ended` or `results_published` state, or start them immediately with `POST /exams/{exam_id}/control/force-start`. These actions create a new `run_number`; all previous student attempts and scores remain preserved. Student attempt limits are counted within the current run. Moderators and students receive HTTP 403 for ended-exam restart/reschedule operations. Archived exams cannot be restarted.

Migration `0008_admin_restart_runs` adds `run_number` to exams and attempts. Deploy backend first and let Alembic upgrade to head before deploying frontend.

# Question Navigation & Answer-Sheet Visibility

## Included in this release

### Question navigator

Every active exam attempt (student, moderator, or administrator) now stores visited question IDs on the attempt record. The exam interface shows a numbered question navigator beside the question card.

- **Green:** the participant has saved an answer for that question.
- **Yellow:** the participant has visited the question but has not saved an answer.
- **Grey:** the participant has not visited the question.
- Selecting a number moves directly to that question.
- The navigator shows total questions, answered questions, visited-but-unanswered questions, and not-visited questions.
- Visit state is persisted by the backend and restored when the participant reloads the exam.

The colour state is based on saved answers and the persisted `visited_question_ids` list. For short answers, a non-empty text value counts as answered; for true/false, a boolean value counts; for MCQ, at least one selected option ID counts.

### Role behavior

- **Administrator:** can enter any non-archived examination through administrator exam mode. Correct answers are always returned to the administrator preview.
- **Moderator:** can enter a live examination through the normal attempt endpoint. Correct answers are visible to moderators. Moderator attempts are not included in student leaderboards because leaderboard queries only rank active student accounts.
- **Student:** never receives answer keys during a live exam. After the exam ends, answer keys are available only under the visibility rules below.

### Student answer-sheet policy

A student may receive answer keys only after the exam is ended, results-published, or archived, and only when one of these conditions is true:

1. The student submitted an attempt and the examiner has not hidden participant answers.
2. The administrator/moderator made the answer sheet public.
3. The administrator/moderator granted answer-sheet access to that individual student.

An explicit individual grant and the public setting override the participant-hide setting. A student who did not participate cannot view an answer sheet unless it is public or that student has an explicit grant. A participant's score is included with the read-only answer sheet when the student has a submitted attempt.

When an examination ends or reaches its scheduled end, any still-in-progress ordinary participant attempts are automatically finalized and scored from the answers saved so far. Administrator preview attempts remain separate and do not enter student rankings.

### Examiner controls

The answer visibility panel is available to administrators and moderators who have the `results.read` permission. It becomes active after the exam ends and provides:

- **Hide answers from participants** — hides answers from students who participated; individual grants and public access are separate overrides.
- **Show answers to participants** — restores the default post-exam access for participants without making the sheet public.
- **Make answers public to all students** — permits any student to view the answer sheet after the exam ends.
- **Stop public access** — disables public access while preserving the normal participant rule.
- **Grant answer access** — grants an individual active student access by email.
- **Revoke** — removes an individual grant.

Moderators need the existing `results.read` permission to change answer visibility or grant/revoke individual access. Administrators bypass permission checks.

## API additions

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/v1/attempts/{attempt_id}/visit/{question_id}` | Persist that the participant visited a question |
| `PATCH` | `/api/v1/exams/{exam_id}/answer-visibility` | Hide participant answers or make answers public |
| `GET` | `/api/v1/exams/{exam_id}/answer-access` | List individual student answer-sheet grants |
| `POST` | `/api/v1/exams/{exam_id}/answer-access` | Grant answer-sheet access by student email |
| `DELETE` | `/api/v1/exams/{exam_id}/answer-access/{student_id}` | Revoke an individual grant |
| `GET` | `/api/v1/exams/{exam_id}/answer-sheet` | Retrieve a permitted read-only answer sheet and participant result |

Existing attempt endpoints are extended:

- `GET /api/v1/attempts/{attempt_id}` now returns `visited_question_ids`, `can_view_answers`, and score fields.
- `GET /api/v1/attempts/{attempt_id}/questions` returns `answer_key` only to administrators/moderators or students who meet the post-exam visibility policy.
- `POST /api/v1/exams/{exam_id}/attempts` accepts both students and moderators. Selected-student access restrictions still apply to students; moderators may supervise live exams.

## Database migration

New Alembic revision: `0007_question_navigation_answer_visibility`

It adds:

- `exams.answers_public` (default `false`)
- `exams.hide_participant_answers` (default `false`)
- `attempts.visited_question_ids` (default empty JSON array)
- `attempts.is_staff_attempt` (marks moderator/admin attempts so they can never enter student leaderboards, even if the account role changes later)
- `answer_visibility_grants` table with unique `(exam_id, student_id)` grants

The migration is additive and preserves existing exams, attempts, answers, and answer keys. The current backend startup lifespan runs pending migrations when `AUTO_MIGRATE=true` (the default). Back up the database before deployment and deploy the backend before the frontend.

## Deployment

1. Back up the production database.
2. Deploy the updated backend and confirm Alembic reaches `0007_question_navigation_answer_visibility`.
3. Deploy the updated frontend.
4. Test a live exam with a student and a moderator.
5. End a test exam and verify default participant answer access.
6. Test Hide answers, Make answers public, individual grant, and revoke.

## Test coverage

The backend suite includes tests for persistent visit state, student answer-key protection during a live exam, post-exam result/answer access, hidden answers, public answer sheets, individual grants, selected-student access with an answer grant, moderator answer visibility and permission checks, manual stop auto-submission, and scheduled-end auto-submission.

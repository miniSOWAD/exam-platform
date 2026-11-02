# MVP feature matrix

| Feature | Included in starter | Notes |
|---|---|---|
| Student self-registration | Yes | Creates student role only |
| Admin bootstrap | Yes | CLI-only initial admin creation |
| Admin-created students | API | `POST /admin/students` |
| Moderator creation | API | Admin only |
| Granular moderator permissions | API foundation | Route-specific enforcement still needs expanding |
| Exam creation/listing | Yes | Basic configuration |
| Question types | Data/API | MCQ, multiple MCQ, true/false, short answer |
| Publish exam | Yes | Requires at least one question |
| Start/pause/resume/end | Yes | REST control endpoints |
| Student exam attempt | Yes | Start, fetch questions, save, submit |
| Objective scoring | Yes | Exact match; short answers normalized exact match |
| Leaderboard | Yes | After results publication |
| PDF subject/chapter/set extraction | Yes | Bengali/English OCR with editable metadata |
| Question and MCQ option extraction | Yes | Structured preview; manual review required |
| Create exam from reviewed PDF | Yes | Creates exam and questions after approval |
| Edit imported question text/options/answer keys | Yes | Dashboard question editor; locked after first attempt |
| Publish validation | Yes | Requires valid answer key for every question |
| Scanned PDF OCR | Yes | Tesseract `ben+eng`, 30-page limit |
| AI diagram/equation interpretation | No | Requires a separate vision/AI pipeline |
| WebSocket live fanout | No | Redis coordination required for production |
| Email verification/password reset | No | Must be added before public launch |
| Audit logs | Schema planning only | Not yet fully wired |

## Owner profile, website content and scheduling additions

| Capability | Current status | Access |
|---|---|---|
| Permanent public site-owner profile (Md Mahruf Alam by default) | Implemented | Public read; Admin edit |
| Admin-managed brand, ribbon, hero, subjects, section copy, feature cards and footer | Implemented | Admin |
| Owner education, institution, photo URL, email, phone and social links | Implemented | Public read; Admin edit |
| Top-right signed-in user avatar/account menu | Implemented | Authenticated users |
| Set/reschedule draft or upcoming exam start/end | Implemented | Admin / moderator with `exam.update` |
| Prevent early manual start before scheduled start | Implemented | Backend enforced |
| Extend duration of upcoming/live/paused exam | Implemented | `exam.update` for upcoming; `exam.live_edit` for live/paused |
| Student server timer synchronization after extension | Implemented | Attempt owner |
| Automatic scheduled start/end worker | Not included | Future enhancement |
| Direct owner photo upload to object storage | Not included; use a public image URL | Future enhancement |

| Feature | v1.2.0 status |
|---|---|
| Student/moderator/admin own profile photo | Implemented; Cloudinary; 300 KiB max |
| Admin site-owner portrait upload | Implemented; Cloudinary; 300 KiB max |
| JPG/JPEG, PNG and WebP validation | Implemented server-side |
| Neon PostgreSQL pooled connection configuration | Implemented |
| Render FastAPI Docker deployment blueprint | Included |

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

from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func
import jwt, fitz, re
from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_token, decode_token
from app.core.config import settings
from app.models.entities import User, Role, Exam, ExamStatus, Question, Attempt, AccessGrant, PermissionGrant, HistoricalResult, SiteContent
from app.schemas.api import RegisterIn, LoginIn, UserOut, ExamIn, QuestionIn, AnswerIn, GrantIn, PermissionIn, PDFCreateExamIn, SiteContentUpdate, ScheduleUpdate, ExtendTimeIn
from app.services.pdf_exam_parser import parse_exam_pdf
from app.services.cloudinary_images import InvalidProfileImage, validate_image_bytes, upload_image, delete_image
from fastapi import Request

router=APIRouter()
DEFAULT_SITE_CONTENT={
    "id":"global", "brand_name":"ExamFlow",
    "ribbon_text":"A calmer space for focused exam preparation",
    "ribbon_right_text":"Mathematics · Physics · Chemistry · Biology",
    "hero_eyebrow":"EXAMINATION PREPARATION, REIMAGINED",
    "hero_title":"Prepare with purpose.", "hero_highlight":"Perform with confidence.",
    "hero_description":"A thoughtful workspace for creating exams, practicing what matters and understanding every result across Mathematics, Physics, Chemistry and Biology.",
    "hero_primary_cta":"Create student account", "hero_secondary_cta":"Sign in",
    "upcoming_title":"Live & upcoming exams", "upcoming_subtitle":"Find an assessment and check your preparation.",
    "calendar_title":"University exam calendar", "calendar_subtitle":"Keep your academic schedule in view and make room for consistent practice.",
    "leaderboard_title":"Leaderboard", "leaderboard_subtitle":"See how students performed in published examinations.",
    "features_title":"Tools for the full examination journey.", "features_subtitle":"From the first question to the final result, keep every part of your learning and assessment workflow connected.",
    "owner_profile_kicker":"SITE OWNER", "owner_expertise_heading":"Areas of expertise",
    "owner_name":"Md Mahruf Alam", "owner_role":"Site Owner · Tutor & Examiner",
    "owner_bio":"I am Md Mahruf Alam, the owner of ExamFlow. I help learners prepare through structured examinations, tutoring and clear performance feedback.",
    "owner_education":"", "owner_institution":"",
    "owner_expertise":["Mathematics","Physics","Chemistry","Biology"],
    "owner_avatar_url":"", "owner_email":"", "owner_phone":"", "owner_website":"",
    "owner_social_links":{},
    "subjects":["Mathematics","Physics","Chemistry","Biology"],
    "feature_cards":[
        {"label":"Exam builder","title":"Build better assessments","description":"Create question sets, configure marks and organize exams by subject, chapter and set."},
        {"label":"Live control","title":"Manage live examinations","description":"Start, pause and resume exams with a server-controlled timer and reliable answer saving."},
        {"label":"Performance","title":"Understand every result","description":"Review scores, compare published rankings and follow performance across attempts."}
    ],
    "footer_text":"Built for focused learning and fair assessment."
}

def _as_utc(value):
    if value is None: return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

def _remaining_seconds(exam, attempt, now=None):
    now=_as_utc(now or datetime.now(timezone.utc))
    started=_as_utc(attempt.started_at)
    if exam.status==ExamStatus.paused and exam.paused_at:
        effective_now=_as_utc(exam.paused_at)
    else:
        effective_now=now
    elapsed=max(0,int((effective_now-started).total_seconds())-int(exam.accumulated_pause_seconds or 0))
    return max(0,int(exam.duration_seconds)-elapsed)

def _site_content_out(row=None):
    if row is None: return dict(DEFAULT_SITE_CONTENT)
    result={key:getattr(row,key) for key in DEFAULT_SITE_CONTENT if key!="id"}
    result["id"]=row.id
    result["updated_at"]=_as_utc(row.updated_at).isoformat() if row.updated_at else None
    return result

PERMISSIONS={"exam.create","exam.update","exam.delete","exam.publish","exam.start","exam.pause","exam.resume","exam.end","exam.live_edit","question.manage","student.read","student.manage","student.import","results.read","results.import","analytics.read","moderator.manage","audit.read"}

def current_user(request: Request, db: Session=Depends(get_db)):
    token=request.cookies.get("access_token")
    if not token: raise HTTPException(401,"Authentication required")
    try: payload=decode_token(token)
    except jwt.PyJWTError: raise HTTPException(401,"Session expired")
    user=db.get(User,payload.get("sub"))
    if not user or not user.active: raise HTTPException(401,"Account unavailable")
    return user

def require(user: User, db: Session, code: str):
    if user.role==Role.admin: return
    if user.role!=Role.moderator: raise HTTPException(403,"Permission denied")
    grant=db.query(PermissionGrant).filter_by(moderator_id=user.id,code=code,active=True).first()
    if not grant: raise HTTPException(403,"Permission denied")

def safe_question(q: Question):
    # Imported PDFs store option keys (A/B/C/D); the student UI consumes option IDs.
    safe_options=[]
    for index, option in enumerate(q.options or []):
        if isinstance(option, dict):
            safe_options.append({"id":str(option.get("id") or option.get("key") or index),"text":str(option.get("text", ""))})
        else:
            safe_options.append({"id":str(index),"text":str(option)})
    return {"id":q.id,"kind":q.kind,"prompt":q.prompt,"options":safe_options,"marks":q.marks,"position":q.position}


def answer_key_missing(question: Question) -> bool:
    key=question.answer_key or {}
    if question.kind in ("mcq", "multiple_mcq"):
        selected=key.get("selected_option_ids") or []
        valid={str(o.get("id") or o.get("key") or i) for i,o in enumerate(question.options or []) if isinstance(o,dict)}
        return not selected or any(str(value) not in valid for value in selected)
    if question.kind == "true_false":
        return not isinstance(key.get("value"), bool)
    if question.kind == "short_answer":
        return not any(str(x).strip() for x in (key.get("accepted_answers") or []))
    return True

@router.get("/site/content")
def get_site_content(db:Session=Depends(get_db)):
    row=db.query(SiteContent).filter_by(id="global").first()
    return _site_content_out(row)

@router.put("/site/content")
def update_site_content(data:SiteContentUpdate,db:Session=Depends(get_db),user:User=Depends(current_user)):
    if user.role!=Role.admin: raise HTTPException(403,"Only the site admin can edit public website content")
    row=db.query(SiteContent).filter_by(id="global").first()
    if row is None:
        row=SiteContent(id="global")
        db.add(row)
    updates=data.model_dump(exclude_unset=True)
    for key,value in updates.items():
        if value is not None: setattr(row,key,value)
    row.updated_by=user.id
    row.updated_at=datetime.now(timezone.utc)
    db.commit(); db.refresh(row)
    return _site_content_out(row)

@router.post("/auth/register", response_model=UserOut, status_code=201)
def register(data:RegisterIn, db:Session=Depends(get_db)):
    email=data.email.lower()
    if db.query(User).filter(func.lower(User.email)==email).first(): raise HTTPException(409,"Email already registered")
    user=User(email=email,full_name=data.full_name,password_hash=hash_password(data.password),role=Role.student)
    db.add(user); db.commit(); db.refresh(user); return user

@router.post("/auth/login")
def login(data:LoginIn,response:Response,db:Session=Depends(get_db)):
    user=db.query(User).filter(func.lower(User.email)==data.email.lower()).first()
    if not user or not verify_password(data.password,user.password_hash) or not user.active: raise HTTPException(401,"Invalid credentials")
    response.set_cookie("access_token",create_token(user.id,user.role.value),httponly=True,secure=settings.cookie_secure,samesite="lax",max_age=settings.access_token_minutes*60,path="/")
    return {"user":UserOut.model_validate(user).model_dump(),"message":"Logged in"}

@router.post("/auth/logout")
def logout(response:Response):
    response.delete_cookie("access_token",path="/"); return {"message":"Logged out"}

@router.get("/auth/me",response_model=UserOut)
def me(user:User=Depends(current_user)): return user


@router.post("/users/me/avatar", response_model=UserOut)
def upload_my_avatar(file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Any signed-in student, moderator or admin can upload their own 300 KB profile photo."""
    try:
        data = file.file.read(settings.max_upload_bytes + 1)
        validated = validate_image_bytes(data, file.content_type)
    except InvalidProfileImage as exc:
        raise HTTPException(413 if "300 KB" in str(exc) else 415, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(400, "Could not read the uploaded image.") from exc
    try:
        folder = f"{settings.cloudinary_folder.strip('/')}/users"
        url, public_id = upload_image(validated, folder=folder, public_id=f"user-{user.id}")
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, "Cloudinary could not store the profile photo. Please try again.") from exc
    user.avatar_url = url
    user.avatar_public_id = public_id
    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/me/avatar", response_model=UserOut)
def remove_my_avatar(db: Session = Depends(get_db), user: User = Depends(current_user)):
    try:
        delete_image(user.avatar_public_id)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, "Cloudinary could not remove the profile photo.") from exc
    user.avatar_url = None
    user.avatar_public_id = None
    db.commit()
    db.refresh(user)
    return user


@router.post("/site/content/owner-avatar")
def upload_owner_avatar(file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Only the site Admin can replace the permanent public owner portrait."""
    if user.role != Role.admin:
        raise HTTPException(403, "Only the site admin can update the owner photo.")
    try:
        data = file.file.read(settings.max_upload_bytes + 1)
        validated = validate_image_bytes(data, file.content_type)
    except InvalidProfileImage as exc:
        raise HTTPException(413 if "300 KB" in str(exc) else 415, str(exc)) from exc
    try:
        folder = f"{settings.cloudinary_folder.strip('/')}/site"
        url, _public_id = upload_image(validated, folder=folder, public_id="owner-profile")
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, "Cloudinary could not store the owner photo. Please try again.") from exc
    row = db.query(SiteContent).filter_by(id="global").first()
    if row is None:
        row = SiteContent(id="global")
        db.add(row)
    row.owner_avatar_url = url
    row.updated_by = user.id
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"owner_avatar_url": url}

@router.get("/users")
def list_users(db:Session=Depends(get_db),user:User=Depends(current_user)):
    require(user,db,"student.read")
    return [{"id":u.id,"full_name":u.full_name,"email":u.email,"role":u.role.value,"active":u.active,"avatar_url":u.avatar_url} for u in db.query(User).order_by(User.created_at.desc()).limit(500).all()]

@router.put("/moderators/{moderator_id}/permissions")
def set_permissions(moderator_id:str,data:PermissionIn,db:Session=Depends(get_db),user:User=Depends(current_user)):
    if user.role!=Role.admin: raise HTTPException(403,"Admin only")
    moderator=db.get(User,moderator_id)
    if not moderator or moderator.role!=Role.moderator: raise HTTPException(404,"Moderator not found")
    if any(c not in PERMISSIONS for c in data.codes): raise HTTPException(422,"Unknown permission")
    db.query(PermissionGrant).filter_by(moderator_id=moderator_id).delete()
    for code in set(data.codes): db.add(PermissionGrant(moderator_id=moderator_id,code=code,granted_by=user.id))
    db.commit(); return {"permissions":data.codes}

@router.post("/admin/students")
def create_student(data:RegisterIn,db:Session=Depends(get_db),user:User=Depends(current_user)):
    if user.role!=Role.admin: raise HTTPException(403,"Admin only")
    if db.query(User).filter(func.lower(User.email)==data.email.lower()).first(): raise HTTPException(409,"Email already exists")
    student=User(email=data.email.lower(),full_name=data.full_name,password_hash=hash_password(data.password),role=Role.student)
    db.add(student); db.commit(); db.refresh(student); return UserOut.model_validate(student)

@router.post("/admin/moderators")
def create_moderator(data:RegisterIn,db:Session=Depends(get_db),user:User=Depends(current_user)):
    if user.role!=Role.admin: raise HTTPException(403,"Admin only")
    if db.query(User).filter(func.lower(User.email)==data.email.lower()).first(): raise HTTPException(409,"Email already exists")
    u=User(email=data.email.lower(),full_name=data.full_name,password_hash=hash_password(data.password),role=Role.moderator)
    db.add(u); db.commit(); db.refresh(u); return UserOut.model_validate(u)

@router.post("/exams",status_code=201)
def create_exam(data:ExamIn,db:Session=Depends(get_db),user:User=Depends(current_user)):
    require(user,db,"exam.create")
    start=_as_utc(data.scheduled_start_at); end=_as_utc(data.scheduled_end_at)
    if start and end and end<=start: raise HTTPException(422,"Scheduled end must be after scheduled start")
    values=data.model_dump()
    values["scheduled_start_at"]=start; values["scheduled_end_at"]=end
    exam=Exam(**values,created_by=user.id); db.add(exam); db.commit(); db.refresh(exam); return exam_out(exam)

def exam_out(e):
    return {"id":e.id,"title":e.title,"description":e.description,"subject":e.subject,"status":e.status.value,"access_mode":e.access_mode,"duration_seconds":e.duration_seconds,"max_attempts":e.max_attempts,"pass_marks":e.pass_marks,"chapter":e.chapter,"set_name":e.set_name,"declared_question_count":e.declared_question_count,"source_file_name":e.source_file_name,"scheduled_start_at":_as_utc(e.scheduled_start_at).isoformat() if e.scheduled_start_at else None,"scheduled_end_at":_as_utc(e.scheduled_end_at).isoformat() if e.scheduled_end_at else None,"time_extension_seconds":e.time_extension_seconds or 0,"question_count":len(e.questions)}

@router.get("/public/exams")
def public_exams(db:Session=Depends(get_db)):
    exams=db.query(Exam).filter(Exam.access_mode=="all_students",Exam.status.in_([ExamStatus.published,ExamStatus.live,ExamStatus.paused])).order_by(Exam.scheduled_start_at.asc().nullslast(),Exam.created_at.desc()).limit(30).all()
    return [exam_out(e) for e in exams]

@router.get("/exams")
def list_exams(db:Session=Depends(get_db),user:User=Depends(current_user)):
    exams=db.query(Exam).filter(Exam.status!=ExamStatus.archived).order_by(Exam.created_at.desc()).limit(100).all()
    if user.role==Role.student:
        visible_statuses={ExamStatus.published,ExamStatus.live,ExamStatus.paused,ExamStatus.ended,ExamStatus.results_published}
        exams=[e for e in exams if e.status in visible_statuses and (e.access_mode=="all_students" or db.query(AccessGrant).filter_by(exam_id=e.id,student_id=user.id,active=True).first())]
    return [exam_out(e) for e in exams]

@router.get("/exams/{exam_id}")
def get_exam(exam_id:str,db:Session=Depends(get_db),user:User=Depends(current_user)):
    e=db.get(Exam,exam_id)
    if not e or (user.role==Role.student and e.status==ExamStatus.draft): raise HTTPException(404,"Exam not found")
    if user.role==Role.student and e.access_mode=="selected_students" and not db.query(AccessGrant).filter_by(exam_id=e.id,student_id=user.id,active=True).first(): raise HTTPException(403,"Exam access not granted")
    return exam_out(e)

@router.post("/exams/{exam_id}/questions")
def add_question(exam_id:str,data:QuestionIn,db:Session=Depends(get_db),user:User=Depends(current_user)):
    require(user,db,"question.manage"); e=db.get(Exam,exam_id)
    if not e: raise HTTPException(404,"Exam not found")
    if e.status in [ExamStatus.live,ExamStatus.paused]: raise HTTPException(409,"Pause the exam before changing its question set")
    q=Question(exam_id=exam_id,**data.model_dump()); db.add(q); db.commit(); db.refresh(q); return safe_question(q)

@router.get("/exams/{exam_id}/questions")
def get_questions(exam_id:str,db:Session=Depends(get_db),user:User=Depends(current_user)):
    require(user,db,"question.manage")
    e=db.get(Exam,exam_id)
    if not e: raise HTTPException(404,"Exam not found")
    return [safe_question(q) for q in db.query(Question).filter_by(exam_id=exam_id).order_by(Question.position).all()]


@router.get("/exams/{exam_id}/questions/manage")
def manage_exam_questions(exam_id:str,db:Session=Depends(get_db),user:User=Depends(current_user)):
    require(user,db,"question.manage")
    if not db.get(Exam,exam_id): raise HTTPException(404,"Exam not found")
    rows=db.query(Question).filter_by(exam_id=exam_id).order_by(Question.position).all()
    return [{**safe_question(q),"answer_key":q.answer_key or {},"negative_marks":q.negative_marks} for q in rows]


@router.patch("/exams/{exam_id}/questions/{question_id}")
def update_exam_question(exam_id:str,question_id:str,data:QuestionIn,db:Session=Depends(get_db),user:User=Depends(current_user)):
    require(user,db,"question.manage")
    exam=db.get(Exam,exam_id)
    question=db.query(Question).filter_by(id=question_id,exam_id=exam_id).first()
    if not exam or not question: raise HTTPException(404,"Exam or question not found")
    if exam.status in [ExamStatus.live,ExamStatus.paused]: raise HTTPException(409,"Pause the examination before editing questions")
    if db.query(Attempt).filter_by(exam_id=exam_id).count(): raise HTTPException(409,"Questions are locked after an examination attempt has started")
    for field,value in data.model_dump().items(): setattr(question,field,value)
    db.commit(); db.refresh(question)
    return {**safe_question(question),"answer_key":question.answer_key or {},"negative_marks":question.negative_marks}

@router.post("/exams/{exam_id}/publish")
def publish_exam(exam_id:str,db:Session=Depends(get_db),user:User=Depends(current_user)):
    require(user,db,"exam.publish"); e=db.get(Exam,exam_id)
    if not e: raise HTTPException(404,"Exam not found")
    if not e.questions: raise HTTPException(400,"Add at least one question")
    missing=[q.position+1 for q in e.questions if answer_key_missing(q)]
    if missing: raise HTTPException(422,{"message":"Add a correct answer key for every question before publishing.","questions_missing_answer_key":missing})
    e.status=ExamStatus.published; db.commit(); return exam_out(e)

@router.post("/exams/{exam_id}/control/{action}")
def control_exam(exam_id:str,action:str,db:Session=Depends(get_db),user:User=Depends(current_user)):
    mapping={"start":("exam.start",ExamStatus.published),"pause":("exam.pause",ExamStatus.live),"resume":("exam.resume",ExamStatus.paused),"end":("exam.end",None)}
    if action not in mapping: raise HTTPException(404,"Unknown action")
    perm,expected=mapping[action]; require(user,db,perm); e=db.query(Exam).filter(Exam.id==exam_id).with_for_update().first()
    if not e: raise HTTPException(404,"Exam not found")
    if expected and e.status!=expected: raise HTTPException(409,f"Cannot {action} exam in {e.status.value} state")
    now=datetime.now(timezone.utc)
    if action=="start" and e.scheduled_start_at and _as_utc(e.scheduled_start_at)>now:
        raise HTTPException(409,f"This examination is scheduled to start at {_as_utc(e.scheduled_start_at).isoformat()}")
    if action=="start": e.status=ExamStatus.live; e.started_at=now
    elif action=="pause": e.status=ExamStatus.paused; e.paused_at=now
    elif action=="resume":
        if e.paused_at: e.accumulated_pause_seconds += int((now-e.paused_at).total_seconds())
        e.paused_at=None; e.status=ExamStatus.live
    else: e.status=ExamStatus.ended; e.ended_at=now; e.paused_at=None
    db.commit(); return exam_out(e)

@router.patch("/exams/{exam_id}/schedule")
def update_exam_schedule(exam_id:str,data:ScheduleUpdate,db:Session=Depends(get_db),user:User=Depends(current_user)):
    require(user,db,"exam.update")
    exam=db.query(Exam).filter(Exam.id==exam_id).with_for_update().first()
    if not exam: raise HTTPException(404,"Exam not found")
    if exam.status not in [ExamStatus.draft,ExamStatus.published]:
        raise HTTPException(409,"Only draft or upcoming examinations can be rescheduled. Use time extension for a running exam.")
    updates=data.model_dump(exclude_unset=True)
    start=_as_utc(updates.get("scheduled_start_at",exam.scheduled_start_at))
    end=_as_utc(updates.get("scheduled_end_at",exam.scheduled_end_at))
    if start and end and end<=start: raise HTTPException(422,"Scheduled end must be after scheduled start")
    if "scheduled_start_at" in updates: exam.scheduled_start_at=start
    if "scheduled_end_at" in updates: exam.scheduled_end_at=end
    db.commit(); db.refresh(exam); return exam_out(exam)

@router.post("/exams/{exam_id}/extend-time")
def extend_exam_time(exam_id:str,data:ExtendTimeIn,db:Session=Depends(get_db),user:User=Depends(current_user)):
    exam=db.query(Exam).filter(Exam.id==exam_id).with_for_update().first()
    if not exam: raise HTTPException(404,"Exam not found")
    if exam.status not in [ExamStatus.published,ExamStatus.live,ExamStatus.paused]:
        raise HTTPException(409,"Time can only be extended for upcoming, live or paused examinations")
    permission="exam.live_edit" if exam.status in [ExamStatus.live,ExamStatus.paused] else "exam.update"
    require(user,db,permission)
    added=data.minutes*60
    exam.duration_seconds+=added
    exam.time_extension_seconds=(exam.time_extension_seconds or 0)+added
    if exam.scheduled_end_at: exam.scheduled_end_at=_as_utc(exam.scheduled_end_at)+timedelta(seconds=added)
    db.commit(); db.refresh(exam)
    return {**exam_out(exam),"added_minutes":data.minutes,"message":"Examination duration extended successfully"}

@router.post("/exams/{exam_id}/access")
def grant_access(exam_id:str,data:GrantIn,db:Session=Depends(get_db),user:User=Depends(current_user)):
    require(user,db,"student.manage")
    if not db.get(Exam,exam_id): raise HTTPException(404,"Exam not found")
    student=db.get(User,data.student_id)
    if not student or student.role!=Role.student: raise HTTPException(404,"Student not found")
    grant=db.query(AccessGrant).filter_by(exam_id=exam_id,student_id=data.student_id).first()
    if grant: grant.active=True
    else: db.add(AccessGrant(exam_id=exam_id,student_id=data.student_id))
    db.commit(); return {"granted":True}

@router.post("/exams/{exam_id}/attempts")
def start_attempt(exam_id:str,db:Session=Depends(get_db),user:User=Depends(current_user)):
    if user.role!=Role.student: raise HTTPException(403,"Students only")
    e=db.get(Exam,exam_id)
    if not e or e.status!=ExamStatus.live: raise HTTPException(409,"Exam is not live")
    if e.access_mode=="selected_students" and not db.query(AccessGrant).filter_by(exam_id=exam_id,student_id=user.id,active=True).first(): raise HTTPException(403,"Access not granted")
    count=db.query(Attempt).filter_by(exam_id=exam_id,student_id=user.id).count()
    if count>=e.max_attempts: raise HTTPException(409,"Attempt limit reached")
    a=Attempt(exam_id=exam_id,student_id=user.id,attempt_number=count+1,max_score=sum(q.marks for q in e.questions)); db.add(a); db.commit(); db.refresh(a)
    return {"attempt_id":a.id,"started_at":a.started_at,"duration_seconds":e.duration_seconds,"remaining_seconds":e.duration_seconds,"exam_status":e.status.value,"server_time":datetime.now(timezone.utc).isoformat()}

@router.get("/attempts/{attempt_id}/questions")
def attempt_questions(attempt_id:str,db:Session=Depends(get_db),user:User=Depends(current_user)):
    a=db.get(Attempt,attempt_id)
    if not a or (a.student_id!=user.id and user.role==Role.student): raise HTTPException(404,"Attempt not found")
    e=db.get(Exam,a.exam_id)
    return [safe_question(q) for q in db.query(Question).filter_by(exam_id=e.id).order_by(Question.position).all()]

@router.get("/attempts/{attempt_id}")
def get_attempt(attempt_id:str,db:Session=Depends(get_db),user:User=Depends(current_user)):
    a=db.get(Attempt,attempt_id)
    if not a or (a.student_id!=user.id and user.role==Role.student): raise HTTPException(404,"Attempt not found")
    exam=db.get(Exam,a.exam_id)
    return {"id":a.id,"exam_id":a.exam_id,"status":a.status,"exam_status":exam.status.value if exam else None,"answers":a.answers,"started_at":a.started_at,"submitted_at":a.submitted_at,"score":a.score,"remaining_seconds":_remaining_seconds(exam,a) if exam and a.status=="in_progress" and exam.status in [ExamStatus.live,ExamStatus.paused] else 0,"duration_seconds":exam.duration_seconds if exam else 0,"server_time":datetime.now(timezone.utc).isoformat()}

@router.put("/attempts/{attempt_id}/answers/{question_id}")
def save_answer(attempt_id:str,question_id:str,data:AnswerIn,db:Session=Depends(get_db),user:User=Depends(current_user)):
    a=db.get(Attempt,attempt_id)
    if not a or a.student_id!=user.id: raise HTTPException(404,"Attempt not found")
    if a.status!="in_progress": raise HTTPException(409,"Attempt is not active")
    e=db.get(Exam,a.exam_id)
    if e.status!=ExamStatus.live: raise HTTPException(409,"Exam is not accepting answers")
    if _remaining_seconds(e,a)<=0: raise HTTPException(409,"Time expired")
    q=db.query(Question).filter_by(id=question_id,exam_id=e.id).first()
    if not q: raise HTTPException(404,"Question not found")
    answers=list(a.answers or []); item=next((x for x in answers if x.get("question_id")==question_id),None)
    if item: item["answer"]=data.answer
    else: answers.append({"question_id":question_id,"answer":data.answer})
    a.answers=answers; db.commit(); return {"saved":True}

def evaluate(q:Question,answer:dict):
    key=q.answer_key or {}
    if q.kind in ("mcq","multiple_mcq"):
        selected=set(answer.get("selected_option_ids",[])); correct=set(key.get("selected_option_ids",[])); return selected==correct
    if q.kind=="true_false": return answer.get("value")==key.get("value")
    if q.kind=="short_answer":
        accepted=[str(x).strip().casefold() for x in key.get("accepted_answers",[])]; return str(answer.get("text","")).strip().casefold() in accepted
    return False

@router.post("/attempts/{attempt_id}/submit")
def submit_attempt(attempt_id:str,db:Session=Depends(get_db),user:User=Depends(current_user)):
    a=db.get(Attempt,attempt_id)
    if not a or a.student_id!=user.id: raise HTTPException(404,"Attempt not found")
    if a.status=="submitted": return {"score":a.score,"status":a.status}
    e=db.get(Exam,a.exam_id); answers={x["question_id"]:x["answer"] for x in (a.answers or [])}; score=0
    for q in e.questions:
        ans=answers.get(q.id)
        if ans is not None: score += q.marks if evaluate(q,ans) else -q.negative_marks
    a.score=max(0,score); a.status="submitted"; a.submitted_at=datetime.now(timezone.utc); db.commit()
    return {"score":a.score,"max_score":a.max_score,"status":a.status}

@router.get("/exams/{exam_id}/leaderboard")
def leaderboard(exam_id:str,db:Session=Depends(get_db),user:User=Depends(current_user)):
    e=db.get(Exam,exam_id)
    if not e or e.status not in [ExamStatus.results_published,ExamStatus.archived]: raise HTTPException(403,"Results not published")
    rows=db.query(Attempt,User).join(User,User.id==Attempt.student_id).filter(Attempt.exam_id==exam_id,Attempt.status=="submitted").order_by(Attempt.score.desc(),Attempt.submitted_at.asc()).limit(500).all()
    best={}
    for a,u in rows:
        if u.id not in best: best[u.id]={"student":u.full_name,"score":a.score,"submitted_at":a.submitted_at}
    result=sorted(best.values(),key=lambda x:(-x["score"],x["submitted_at"] or datetime.max.replace(tzinfo=timezone.utc)))
    return [{"rank":i+1,"student":x["student"],"score":x["score"]} for i,x in enumerate(result)]

@router.post("/exams/{exam_id}/publish-results")
def publish_results(exam_id:str,db:Session=Depends(get_db),user:User=Depends(current_user)):
    require(user,db,"results.read"); e=db.get(Exam,exam_id)
    if not e or e.status!=ExamStatus.ended: raise HTTPException(409,"Exam must be ended")
    e.status=ExamStatus.results_published; db.commit(); return {"published":True}

@router.post("/imports/pdf/preview")
async def preview_exam_pdf(file:UploadFile=File(...),db:Session=Depends(get_db),user:User=Depends(current_user)):
    require(user,db,"question.manage")
    if file.content_type!="application/pdf" and not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(415,"PDF files only")
    raw=await file.read(settings.max_upload_mb*1024*1024+1)
    if len(raw)>settings.max_upload_mb*1024*1024: raise HTTPException(413,"File too large")
    try:
        return parse_exam_pdf(raw,file.filename or "uploaded.pdf",max_pages=30,dpi=240)
    except ValueError as exc:
        raise HTTPException(400,str(exc))
    except Exception as exc:
        # Keep parser/OCR internals out of the response, but explain the missing dependency.
        if "tesseract" in str(exc).lower() or "executable" in str(exc).lower():
            raise HTTPException(503,"Bengali OCR is unavailable. Deploy the backend image with Tesseract and Bengali language data installed.")
        raise HTTPException(422,"Could not extract structured questions from this PDF. Try a clearer PDF or use manual question entry.")


@router.post("/imports/pdf/create-exam",status_code=201)
def create_exam_from_pdf(data:PDFCreateExamIn,db:Session=Depends(get_db),user:User=Depends(current_user)):
    require(user,db,"exam.create")
    require(user,db,"question.manage")
    if not data.questions:
        raise HTTPException(422,"At least one reviewed question is required")
    title=data.title.strip()
    if len(title)<3: raise HTTPException(422,"Exam title is too short")
    if data.publish_immediately:
        require(user,db,"exam.publish")
        missing=[]
        for position,item in enumerate(data.questions):
            candidate=Question(kind=item.kind, options=item.options, answer_key=item.answer_key, position=position)
            if answer_key_missing(candidate): missing.append(item.number)
        if missing: raise HTTPException(422,{"message":"Set a correct answer for every question before publishing.","questions_missing_answer_key":missing})
    exam=Exam(
        title=title, description="Created from a reviewed PDF import.", subject=data.subject.strip() or "General",
        chapter=data.chapter, set_name=data.set_name, declared_question_count=data.declared_question_count, source_file_name=data.source_file_name,
        duration_seconds=data.duration_minutes*60, max_attempts=data.max_attempts,
        pass_marks=0, access_mode=data.access_mode, created_by=user.id,
        status=ExamStatus.published if data.publish_immediately else ExamStatus.draft,
    )
    db.add(exam)
    db.flush()
    for position,item in enumerate(data.questions):
        db.add(Question(
            exam_id=exam.id, kind=item.kind, prompt=item.prompt.strip(), options=item.options,
            answer_key=item.answer_key, marks=item.marks, negative_marks=item.negative_marks,
            position=position,
        ))
    db.commit(); db.refresh(exam)
    return exam_out(exam)


@router.post("/imports/pdf")
async def import_pdf(file:UploadFile=File(...),kind:str="questions",db:Session=Depends(get_db),user:User=Depends(current_user)):
    # Backwards-compatible endpoint for legacy roster/result text previews.
    require(user,db,"student.import" if kind!="questions" else "question.manage")
    if file.content_type!="application/pdf" and not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(415,"PDF files only")
    raw=await file.read(settings.max_upload_mb*1024*1024+1)
    if len(raw)>settings.max_upload_mb*1024*1024: raise HTTPException(413,"File too large")
    try:
        doc=fitz.open(stream=raw,filetype="pdf"); pages=[p.get_text("text") for p in doc]
    except Exception: raise HTTPException(400,"Could not read PDF")
    text="\n".join(pages)
    return {"filename":file.filename,"kind":kind,"pages":len(pages),"extracted_text":text[:100000],"message":"Text preview only. For exam creation use /imports/pdf/preview, review the extracted metadata/questions, then /imports/pdf/create-exam."}

@router.get("/health")
def health(): return {"status":"ok","service":"exam-platform-api"}

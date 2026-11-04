from datetime import datetime, timezone, timedelta
import asyncio
from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, File, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
import jwt, fitz, re
from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_token, decode_token
from app.core.config import settings
from app.models.entities import User, Role, Exam, ExamStatus, Question, Attempt, AccessGrant, PermissionGrant, HistoricalResult, SiteContent, LeaderboardEntry, LeaderboardExclusion
from app.schemas.api import RegisterIn, LoginIn, UserOut, ExamIn, QuestionIn, AnswerIn, GrantIn, PermissionIn, PDFCreateExamIn, SiteContentUpdate, ScheduleUpdate, ExtendTimeIn, AnswerKeyApplyIn, DurationUpdate, CreateManagedUserIn, UserStatusUpdate, UserRoleUpdate, LeaderboardEntryCreate, LeaderboardRemoveIn
from app.services.pdf_exam_parser import parse_exam_pdf, OCRUnavailableError, OCRServiceError
from app.services.answer_key_parser import extract_answer_key_file
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
    response.set_cookie("access_token",create_token(user.id,user.role.value),httponly=True,secure=(settings.cookie_secure or settings.environment.lower() in {"production", "prod"}),samesite="lax",max_age=settings.access_token_minutes*60,path="/")
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

@router.get("/admin/users")
def list_admin_users(
    role: str | None = Query(default=None),
    search: str = Query(default="", max_length=160),
    include_inactive: bool = Query(default=True),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    if user.role != Role.admin:
        raise HTTPException(403, "Admin only")
    query = db.query(User).filter(User.role.in_([Role.student, Role.moderator]))
    if role:
        if role not in (Role.student.value, Role.moderator.value):
            raise HTTPException(422, "Role must be student or moderator")
        query = query.filter(User.role == Role(role))
    if not include_inactive:
        query = query.filter(User.active.is_(True))
    if search.strip():
        term = f"%{search.strip().lower()}%"
        query = query.filter(or_(func.lower(User.full_name).like(term), func.lower(User.email).like(term)))
    rows = query.order_by(User.created_at.desc()).limit(1000).all()
    return [{
        "id": item.id, "full_name": item.full_name, "email": item.email,
        "role": item.role.value, "active": item.active,
        "avatar_url": item.avatar_url,
        "created_at": _as_utc(item.created_at).isoformat() if item.created_at else None,
    } for item in rows]


@router.post("/admin/users", status_code=201, response_model=UserOut)
def create_managed_user(data: CreateManagedUserIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.role != Role.admin:
        raise HTTPException(403, "Admin only")
    email = data.email.lower()
    if db.query(User).filter(func.lower(User.email) == email).first():
        raise HTTPException(409, "Email already registered")
    created = User(
        email=email, full_name=data.full_name.strip(),
        password_hash=hash_password(data.password), role=Role(data.role), active=True,
    )
    db.add(created)
    db.commit()
    db.refresh(created)
    return created


@router.patch("/admin/users/{user_id}/status")
def update_managed_user_status(user_id: str, data: UserStatusUpdate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.role != Role.admin:
        raise HTTPException(403, "Admin only")
    target = db.get(User, user_id)
    if not target or target.role == Role.admin:
        raise HTTPException(404, "Student or moderator not found")
    target.active = data.active
    db.commit()
    return {"id": target.id, "active": target.active, "message": "Account access updated."}


@router.patch("/admin/users/{user_id}/role")
def update_managed_user_role(user_id: str, data: UserRoleUpdate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.role != Role.admin:
        raise HTTPException(403, "Admin only")
    target = db.get(User, user_id)
    if not target or target.role == Role.admin:
        raise HTTPException(404, "Student or moderator not found")
    new_role = Role(data.role)
    if target.role == new_role:
        return {"id": target.id, "role": target.role.value, "message": "Role is already set."}
    if new_role == Role.student:
        db.query(PermissionGrant).filter_by(moderator_id=target.id).delete(synchronize_session=False)
    target.role = new_role
    db.commit()
    return {"id": target.id, "role": target.role.value, "message": "User role updated. Newly promoted moderators have no permissions until the admin grants them."}


@router.delete("/admin/users/{user_id}")
def remove_managed_user(user_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Permanently remove a student/moderator and their personal exam attempts."""
    if user.role != Role.admin:
        raise HTTPException(403, "Admin only")
    target = db.get(User, user_id)
    if not target or target.role == Role.admin:
        raise HTTPException(404, "Student or moderator not found")
    if target.id == user.id:
        raise HTTPException(409, "You cannot remove your own administrator account")

    # Preserve exams and administrative records created by the removed account.
    db.query(Exam).filter_by(created_by=target.id).update({Exam.created_by: user.id}, synchronize_session=False)
    db.query(SiteContent).filter_by(updated_by=target.id).update({SiteContent.updated_by: user.id}, synchronize_session=False)
    db.query(HistoricalResult).filter_by(imported_by=target.id).update({HistoricalResult.imported_by: user.id}, synchronize_session=False)
    db.query(PermissionGrant).filter_by(granted_by=target.id).update({PermissionGrant.granted_by: user.id}, synchronize_session=False)
    db.query(LeaderboardEntry).filter_by(created_by=target.id).update({LeaderboardEntry.created_by: user.id}, synchronize_session=False)
    db.query(LeaderboardExclusion).filter_by(created_by=target.id).update({LeaderboardExclusion.created_by: user.id}, synchronize_session=False)

    # Remove user-linked records and attempts so deleted users no longer appear in rankings.
    db.query(PermissionGrant).filter_by(moderator_id=target.id).delete(synchronize_session=False)
    db.query(AccessGrant).filter_by(student_id=target.id).delete(synchronize_session=False)
    db.query(Attempt).filter_by(student_id=target.id).delete(synchronize_session=False)
    db.query(LeaderboardEntry).filter_by(student_id=target.id).delete(synchronize_session=False)
    db.query(LeaderboardExclusion).filter_by(student_id=target.id).delete(synchronize_session=False)
    db.delete(target)
    db.commit()
    return {"removed": True, "message": "Account and its personal exam attempts were removed."}


@router.post("/exams",status_code=201)
def create_exam(data:ExamIn,db:Session=Depends(get_db),user:User=Depends(current_user)):
    require(user,db,"exam.create")
    start=_as_utc(data.scheduled_start_at); end=_as_utc(data.scheduled_end_at)
    if start and end and end<=start: raise HTTPException(422,"Scheduled end must be after scheduled start")
    values=data.model_dump()
    values["scheduled_start_at"]=start; values["scheduled_end_at"]=end
    exam=Exam(**values,created_by=user.id); db.add(exam); db.commit(); db.refresh(exam); return exam_out(exam)

def exam_out(e):
    return {"id":e.id,"title":e.title,"description":e.description,"subject":e.subject,"status":e.status.value,"access_mode":e.access_mode,"duration_seconds":e.duration_seconds,"max_attempts":e.max_attempts,"pass_marks":e.pass_marks,"chapter":e.chapter,"set_name":e.set_name,"paper":e.paper,"declared_question_count":e.declared_question_count,"source_file_name":e.source_file_name,"scheduled_start_at":_as_utc(e.scheduled_start_at).isoformat() if e.scheduled_start_at else None,"scheduled_end_at":_as_utc(e.scheduled_end_at).isoformat() if e.scheduled_end_at else None,"time_extension_seconds":e.time_extension_seconds or 0,"question_count":len(e.questions)}

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
    return [safe_question(q) for q in db.query(Question).filter_by(exam_id=exam_id).order_by(Question.position, Question.id).all()]


@router.get("/exams/{exam_id}/questions/manage")
def manage_exam_questions(exam_id:str,db:Session=Depends(get_db),user:User=Depends(current_user)):
    require(user,db,"question.manage")
    if not db.get(Exam,exam_id): raise HTTPException(404,"Exam not found")
    rows=db.query(Question).filter_by(exam_id=exam_id).order_by(Question.position, Question.id).all()
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

def _answer_key_option_id(option, index: int) -> str:
    if isinstance(option, dict):
        return str(option.get("id") or option.get("key") or index)
    return str(index)


def _ensure_answer_key_editable(exam: Exam, db: Session) -> None:
    if exam.status in [ExamStatus.live, ExamStatus.paused, ExamStatus.ended, ExamStatus.results_published, ExamStatus.archived]:
        raise HTTPException(409, "Answer keys cannot be changed after an examination has started or ended.")
    if db.query(Attempt).filter_by(exam_id=exam.id).count():
        raise HTTPException(409, "Answer keys are locked because a student attempt has already started.")


@router.post("/exams/{exam_id}/answer-key/preview")
async def preview_exam_answer_key(
    exam_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Parse a numbered answer-only TXT/PDF and preview question matches without saving."""
    require(user, db, "question.manage")
    exam = db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(404, "Examination not found")
    _ensure_answer_key_editable(exam, db)

    filename = file.filename or "answer-key"
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in {"pdf", "txt"}:
        raise HTTPException(415, "Upload an answer-key PDF or TXT file.")
    max_bytes = (settings.max_pdf_upload_mb if extension == "pdf" else 2) * 1024 * 1024
    raw = await file.read(max_bytes + 1)
    if len(raw) > max_bytes:
        limit = f"{settings.max_pdf_upload_mb} MB" if extension == "pdf" else "2 MB"
        raise HTTPException(413, f"The answer-key file exceeds the {limit} upload limit.")

    try:
        parsed = await asyncio.to_thread(
            extract_answer_key_file,
            raw,
            filename,
            settings.ocr_space_api_key,
            settings.ocr_space_engine,
            settings.ocr_space_timeout_seconds,
            30,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except OCRUnavailableError as exc:
        raise HTTPException(503, str(exc)) from exc
    except OCRServiceError as exc:
        raise HTTPException(502, f"Answer-key OCR failed: {exc}") from exc

    rows = db.query(Question).filter_by(exam_id=exam_id).order_by(Question.position, Question.id).all()
    preview_answers = []
    detected_numbers = set()
    for entry in parsed["entries"]:
        number = entry["question_number"]
        detected_numbers.add(number)
        indices = entry["option_indices"]
        labels = entry["option_labels"]
        status = "ready"
        reason = None
        current_labels = []

        if number > len(rows):
            status = "out_of_range"
            reason = f"This examination has only {len(rows)} questions."
        else:
            question = rows[number - 1]
            if question.kind not in ("mcq", "multiple_mcq"):
                status = "unsupported_question_type"
                reason = "This question is not an MCQ."
            elif any(index >= len(question.options or []) for index in indices):
                status = "invalid_option"
                reason = "The answer refers to an option that does not exist for this question."
            elif question.kind == "mcq" and len(set(indices)) > 1:
                status = "conflict"
                reason = "More than one different answer was supplied for a single-correct MCQ."
            else:
                selected = set(str(value) for value in ((question.answer_key or {}).get("selected_option_ids") or []))
                for option_index, option in enumerate(question.options or []):
                    if _answer_key_option_id(option, option_index) in selected:
                        current_labels.append(chr(ord("A") + option_index))

        preview_answers.append({
            "question_number": number,
            "option_labels": labels,
            "option_indices": indices,
            "status": status,
            "reason": reason,
            "current_option_labels": current_labels,
        })

    ready_count = sum(1 for item in preview_answers if item["status"] == "ready")
    return {
        "filename": filename,
        "source_type": parsed["source_type"],
        "ocr_used": parsed["ocr_used"],
        "ocr_engine": parsed["ocr_engine"],
        "pages": parsed["pages"],
        "question_count": len(rows),
        "detected_count": len(preview_answers),
        "ready_count": ready_count,
        "answers": preview_answers,
        "missing_question_numbers": [number for number in range(1, len(rows) + 1) if number not in detected_numbers],
    }


@router.post("/exams/{exam_id}/answer-key/apply")
def apply_exam_answer_key(
    exam_id: str,
    data: AnswerKeyApplyIn,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Apply validated option indices to the matching question serials atomically."""
    require(user, db, "question.manage")
    exam = db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(404, "Examination not found")
    _ensure_answer_key_editable(exam, db)

    rows = db.query(Question).filter_by(exam_id=exam_id).order_by(Question.position, Question.id).all()
    seen_numbers = set()
    updates = []
    for entry in data.answers:
        number = entry.question_number
        if number in seen_numbers:
            raise HTTPException(422, f"Question {number} appears more than once in the answer-key import.")
        seen_numbers.add(number)
        if number > len(rows):
            raise HTTPException(422, f"Question {number} does not exist in this examination.")
        question = rows[number - 1]
        if question.kind not in ("mcq", "multiple_mcq"):
            raise HTTPException(422, f"Question {number} is not an MCQ and cannot receive an A/B/C/D answer.")
        indices = entry.option_indices
        if len(set(indices)) != len(indices):
            raise HTTPException(422, f"Question {number} contains duplicate option labels.")
        if question.kind == "mcq" and len(indices) != 1:
            raise HTTPException(422, f"Question {number} is single-correct and must have exactly one answer.")
        if any(index < 0 or index >= len(question.options or []) for index in indices):
            raise HTTPException(422, f"Question {number} refers to an option that does not exist.")
        option_ids = [_answer_key_option_id(question.options[index], index) for index in indices]
        updates.append((number, question, option_ids))

    try:
        for _, question, option_ids in updates:
            question.answer_key = {**(question.answer_key or {}), "selected_option_ids": option_ids}
        db.commit()
    except Exception:
        db.rollback()
        raise

    refreshed_rows = db.query(Question).filter_by(exam_id=exam_id).order_by(Question.position, Question.id).all()
    unanswered = [index + 1 for index, question in enumerate(refreshed_rows) if answer_key_missing(question)]
    return {
        "applied_count": len(updates),
        "updated_question_numbers": [number for number, _, _ in updates],
        "unanswered_question_numbers": unanswered,
        "message": f"Answer keys updated for {len(updates)} question(s).",
    }


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

@router.patch("/exams/{exam_id}/duration")
def update_exam_duration(exam_id: str, data: DurationUpdate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Set an absolute exam duration; admins may increase or reduce it while live."""
    if user.role != Role.admin:
        raise HTTPException(403, "Only the site admin can change an examination's total duration")
    exam = db.query(Exam).filter(Exam.id == exam_id).with_for_update().first()
    if not exam:
        raise HTTPException(404, "Exam not found")
    if exam.status not in [ExamStatus.draft, ExamStatus.published, ExamStatus.live, ExamStatus.paused]:
        raise HTTPException(409, "Duration cannot be changed after the examination has ended")
    old_seconds = int(exam.duration_seconds)
    new_seconds = int(data.duration_minutes) * 60
    delta = new_seconds - old_seconds
    exam.duration_seconds = new_seconds
    if delta > 0:
        exam.time_extension_seconds = int(exam.time_extension_seconds or 0) + delta
    if exam.scheduled_end_at:
        exam.scheduled_end_at = _as_utc(exam.scheduled_end_at) + timedelta(seconds=delta)
    db.flush()
    active_attempts = db.query(Attempt).filter_by(exam_id=exam.id, status="in_progress").all()
    expired_attempts = sum(1 for attempt in active_attempts if _remaining_seconds(exam, attempt) <= 0)
    db.commit()
    db.refresh(exam)
    return {
        **exam_out(exam), "previous_duration_seconds": old_seconds,
        "duration_change_seconds": delta, "active_attempts": len(active_attempts),
        "attempts_now_out_of_time": expired_attempts,
        "message": "Examination duration updated successfully.",
    }


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
    return [safe_question(q) for q in db.query(Question).filter_by(exam_id=e.id).order_by(Question.position, Question.id).all()]

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

def _normalize_paper(value: str | None) -> str | None:
    if not value:
        return None
    raw = value.strip().casefold()
    if any(token in raw for token in ("2nd", "second", "দ্বিতীয়", "দ্বিতীয়", "২য়", "২য়", "২য় পত্র", "paper 2")):
        return "2nd Paper"
    if any(token in raw for token in ("1st", "first", "প্রথম", "১ম", "paper 1")):
        return "1st Paper"
    return None


def _exam_paper(exam: Exam) -> str | None:
    explicit = _normalize_paper(exam.paper)
    if explicit:
        return explicit
    haystack = " ".join(str(value or "") for value in (exam.title, exam.subject, exam.chapter, exam.set_name))
    return _normalize_paper(haystack)


def _leaderboard_scope_matches(scope: str, exam: Exam, exam_id: str | None, paper: str | None, subject: str | None) -> bool:
    if scope == "exam":
        return exam.id == exam_id
    if scope == "paper":
        return _exam_paper(exam) == paper and (not subject or exam.subject.strip().casefold() == subject.strip().casefold())
    return exam.subject.strip().casefold() == (subject or "").strip().casefold()


def _entry_matches_scope(entry: LeaderboardEntry, scope: str, exam_id: str | None, paper: str | None, subject: str | None) -> bool:
    if entry.scope != scope:
        return False
    if scope == "exam":
        return entry.exam_id == exam_id
    if scope == "paper":
        return entry.paper == paper and (not subject or (entry.subject or "").strip().casefold() == subject.strip().casefold())
    return (entry.subject or "").strip().casefold() == (subject or "").strip().casefold()


def _build_leaderboard_rows(db: Session, scope: str, exam_id: str | None = None, paper: str | None = None, subject: str | None = None):
    matching_exams = [exam for exam in db.query(Exam).all() if _leaderboard_scope_matches(scope, exam, exam_id, paper, subject)]
    exam_map = {exam.id: exam for exam in matching_exams}
    if scope == "exam" and exam_id not in exam_map:
        raise HTTPException(404, "Examination not found")

    exclusions = db.query(LeaderboardExclusion).filter_by(scope=scope).all()
    excluded_ids = set()
    for item in exclusions:
        if scope == "exam" and item.exam_id == exam_id:
            excluded_ids.add(item.student_id)
        elif scope == "paper" and item.paper == paper and (not subject or (item.subject or "").casefold() == subject.casefold()):
            excluded_ids.add(item.student_id)
        elif scope == "subject" and (item.subject or "").casefold() == (subject or "").casefold():
            excluded_ids.add(item.student_id)

    attempt_rows = []
    if exam_map:
        attempt_rows = db.query(Attempt, User, Exam).join(User, User.id == Attempt.student_id).join(Exam, Exam.id == Attempt.exam_id).filter(
            Attempt.exam_id.in_(list(exam_map.keys())),
            Attempt.status == "submitted", User.active.is_(True), User.role == Role.student,
        ).all()
    best_per_exam_student = {}
    question_cache = {}
    for attempt, student, exam in attempt_rows:
        if exam.id not in exam_map or student.id in excluded_ids:
            continue
        if exam.id not in question_cache:
            question_cache[exam.id] = db.query(Question).filter_by(exam_id=exam.id).order_by(Question.position).all()
        questions = question_cache[exam.id]
        answer_map = {item.get("question_id"): item.get("answer", {}) for item in (attempt.answers or []) if isinstance(item, dict)}
        answered_questions = [question for question in questions if question.id in answer_map]
        correct_count = sum(1 for question in answered_questions if evaluate(question, answer_map[question.id]))
        performance = {
            "attempt": attempt, "student": student, "exam": exam,
            "correct_count": correct_count, "answered_count": len(answered_questions),
            "total_questions": len(questions),
            "max_score": float(attempt.max_score or sum(float(question.marks or 0) for question in questions)),
        }
        key = (student.id, exam.id)
        current = best_per_exam_student.get(key)
        current_score = float(current["attempt"].score or 0) if current else -1
        candidate_score = float(attempt.score or 0)
        current_accuracy = (current["correct_count"] / current["answered_count"]) if current and current["answered_count"] else 0
        candidate_accuracy = correct_count / len(answered_questions) if answered_questions else 0
        if current is None or (candidate_score, candidate_accuracy) > (current_score, current_accuracy):
            best_per_exam_student[key] = performance

    aggregated = {}
    for (student_id, _exam_id), item in best_per_exam_student.items():
        student = item["student"]
        row = aggregated.setdefault(student_id, {
            "id": f"attempt:{student_id}", "student_id": student_id,
            "student": student.full_name, "email": student.email,
            "score": 0.0, "max_score": 0.0, "correct_count": 0,
            "answered_count": 0, "total_questions": 0, "exam_count": 0, "source": "attempt",
            "submitted_at": None,
        })
        row["score"] += float(item["attempt"].score or 0)
        row["max_score"] += float(item["max_score"] or 0)
        row["correct_count"] += int(item["correct_count"])
        row["answered_count"] += int(item["answered_count"])
        row["total_questions"] += int(item["total_questions"])
        row["exam_count"] += 1
        submitted = _as_utc(item["attempt"].submitted_at)
        if submitted and (row["submitted_at"] is None or submitted < row["submitted_at"]):
            row["submitted_at"] = submitted

    manual_entries = db.query(LeaderboardEntry).all()
    for entry in manual_entries:
        if not _entry_matches_scope(entry, scope, exam_id, paper, subject):
            continue
        if entry.student_id and entry.student_id in excluded_ids:
            continue
        linked_user = db.get(User, entry.student_id) if entry.student_id else None
        if linked_user and not linked_user.active:
            continue
        identity = entry.student_id
        manual_score = float(entry.score or 0)
        if identity:
            row = aggregated.get(identity)
            if row is None:
                row = {
                    "id": identity, "entry_id": entry.id, "student_id": identity,
                    "student": linked_user.full_name if linked_user else entry.display_name,
                    "email": linked_user.email if linked_user else (entry.student_identifier or ""),
                    "score": manual_score, "max_score": float(entry.max_score or 0),
                    "correct_count": 0, "answered_count": 0, "total_questions": 0, "exam_count": 0,
                    "source": "manual", "submitted_at": _as_utc(entry.created_at),
                    "manual_accuracy": (manual_score / float(entry.max_score) * 100) if entry.max_score else None,
                }
                aggregated[identity] = row
            else:
                if manual_score > float(row["score"]):
                    row["score"] = manual_score
                    row["max_score"] = float(entry.max_score or 0)
                    row["correct_count"] = 0
                    row["answered_count"] = 0
                    row["total_questions"] = 0
                    row["manual_accuracy"] = (manual_score / float(entry.max_score) * 100) if entry.max_score else None
                row["source"] = "combined"
                row["manual_entry_id"] = entry.id
                if entry.student_identifier:
                    row["student_identifier"] = entry.student_identifier
        else:
            row_id = f"manual:{entry.id}"
            aggregated[row_id] = {
                "id": row_id, "entry_id": entry.id, "student_id": None,
                "student": entry.display_name, "email": entry.student_identifier or "",
                "score": manual_score, "max_score": float(entry.max_score or 0),
                "correct_count": 0, "answered_count": 0, "total_questions": 0, "exam_count": 0,
                "source": "manual", "submitted_at": _as_utc(entry.created_at),
                "manual_accuracy": (manual_score / float(entry.max_score) * 100) if entry.max_score else None,
            }

    rows = list(aggregated.values())
    for row in rows:
        row["accuracy"] = round((row["correct_count"] / row["total_questions"] * 100), 2) if row["total_questions"] else (
            round(row["manual_accuracy"], 2) if row.get("manual_accuracy") is not None else None
        )
        row["score"] = round(float(row["score"]), 2)
        row["max_score"] = round(float(row["max_score"]), 2) if row["max_score"] else None
        row["submitted_at"] = row["submitted_at"].isoformat() if row["submitted_at"] else None
    rows.sort(key=lambda row: (-row["score"], -(row["accuracy"] or 0), row["student"].casefold()))
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
    return rows


@router.get("/exams/{exam_id}/leaderboard")
def leaderboard(exam_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    exam = db.get(Exam, exam_id)
    if not exam or exam.status not in [ExamStatus.results_published, ExamStatus.archived]:
        raise HTTPException(403, "Results not published")
    rows = _build_leaderboard_rows(db, "exam", exam_id=exam_id)
    return [{"rank": row["rank"], "student": row["student"], "score": row["score"], "max_score": row["max_score"], "accuracy": row["accuracy"]} for row in rows]


@router.get("/admin/leaderboards")
def get_admin_leaderboard(
    scope: str = Query(default="exam"), exam_id: str | None = None,
    paper: str | None = None, subject: str | None = None,
    db: Session = Depends(get_db), user: User = Depends(current_user),
):
    if user.role != Role.admin:
        raise HTTPException(403, "Admin only")
    if scope not in ("exam", "paper", "subject"):
        raise HTTPException(422, "Scope must be exam, paper or subject")
    normalized_paper = _normalize_paper(paper) if paper else None
    if scope == "exam" and not exam_id:
        raise HTTPException(422, "Select an examination")
    if scope == "paper" and not normalized_paper:
        raise HTTPException(422, "Select 1st Paper or 2nd Paper")
    if scope == "subject" and not (subject or "").strip():
        raise HTTPException(422, "Select a subject")
    rows = _build_leaderboard_rows(db, scope, exam_id=exam_id, paper=normalized_paper, subject=subject)
    return {"scope": scope, "exam_id": exam_id, "paper": normalized_paper, "subject": subject, "total": len(rows), "rows": rows}


@router.post("/admin/leaderboards/entries", status_code=201)
def create_admin_leaderboard_entry(data: LeaderboardEntryCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.role != Role.admin:
        raise HTTPException(403, "Admin only")
    exam = db.get(Exam, data.exam_id) if data.exam_id else None
    if data.scope == "exam" and not exam:
        raise HTTPException(404, "Examination not found")
    identifier = (data.student_identifier or "").strip()
    linked_student = None
    if identifier:
        linked_student = db.query(User).filter(
            User.role == Role.student,
            or_(func.lower(User.email) == identifier.lower(), func.lower(User.full_name) == identifier.lower(), User.id == identifier),
        ).first()
        if linked_student and not linked_student.active:
            raise HTTPException(409, "The matched student account is blocked")
    paper_value = _normalize_paper(data.paper) if data.paper else None
    subject_value = (data.subject or (exam.subject if exam else "")).strip() or None
    entry = LeaderboardEntry(
        scope=data.scope, display_name=data.display_name.strip(),
        student_identifier=identifier or None, student_id=linked_student.id if linked_student else None,
        exam_id=exam.id if exam else None, paper=paper_value,
        subject=subject_value, score=float(data.score), max_score=float(data.max_score) if data.max_score is not None else None,
        created_by=user.id,
    )
    db.add(entry)
    if linked_student:
        exclusions = db.query(LeaderboardExclusion).filter_by(scope=data.scope, student_id=linked_student.id).all()
        for exclusion in exclusions:
            same_target = (data.scope == "exam" and exclusion.exam_id == data.exam_id) or (data.scope == "paper" and exclusion.paper == paper_value and (not subject_value or (exclusion.subject or "").casefold() == subject_value.casefold())) or (data.scope == "subject" and (exclusion.subject or "").casefold() == (subject_value or "").casefold())
            if same_target:
                db.delete(exclusion)
    db.commit()
    db.refresh(entry)
    return {"id": entry.id, "display_name": entry.display_name, "scope": entry.scope, "message": "Leaderboard entry added and will be ranked automatically."}


@router.post("/admin/leaderboards/remove")
def remove_admin_leaderboard_entry(data: LeaderboardRemoveIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.role != Role.admin:
        raise HTTPException(403, "Admin only")
    entry = db.get(LeaderboardEntry, data.entry_id) if data.entry_id else None
    student_id = data.student_id or (entry.student_id if entry else None)
    if data.entry_id and (not entry or not _entry_matches_scope(entry, data.scope, data.exam_id, _normalize_paper(data.paper) if data.paper else None, data.subject)):
        raise HTTPException(404, "Leaderboard entry not found")
    if student_id:
        student = db.get(User, student_id)
        if not student:
            raise HTTPException(404, "Student not found")
        normalized_paper = _normalize_paper(data.paper) if data.paper else None
        existing = db.query(LeaderboardExclusion).filter_by(scope=data.scope, student_id=student_id).all()
        already_excluded = any(
            (data.scope == "exam" and item.exam_id == data.exam_id) or
            (data.scope == "paper" and item.paper == normalized_paper and (not data.subject or (item.subject or "").casefold() == data.subject.casefold())) or
            (data.scope == "subject" and (item.subject or "").casefold() == (data.subject or "").casefold())
            for item in existing
        )
        if not already_excluded:
            db.add(LeaderboardExclusion(scope=data.scope, student_id=student_id, exam_id=data.exam_id if data.scope == "exam" else None,
                paper=normalized_paper if data.scope == "paper" else None, subject=data.subject if data.scope in ("paper", "subject") else None, created_by=user.id))
        manual = db.query(LeaderboardEntry).filter_by(student_id=student_id, scope=data.scope).all()
        for item in manual:
            if _entry_matches_scope(item, data.scope, data.exam_id, normalized_paper, data.subject):
                db.delete(item)
    elif entry:
        db.delete(entry)
    db.commit()
    return {"removed": True, "message": "The selected name was removed from this leaderboard."}

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
    max_bytes=settings.max_pdf_upload_mb*1024*1024
    raw=await file.read(max_bytes+1)
    if len(raw)>max_bytes: raise HTTPException(413,f"PDF exceeds the {settings.max_pdf_upload_mb} MB upload limit")
    try:
        return await asyncio.to_thread(
            parse_exam_pdf,
            raw,
            file.filename or "uploaded.pdf",
            30,
            240,
            settings.ocr_space_api_key,
            settings.ocr_space_engine,
            settings.ocr_space_timeout_seconds,
        )
    except ValueError as exc:
        raise HTTPException(400,str(exc))
    except OCRUnavailableError as exc:
        raise HTTPException(503,str(exc))
    except OCRServiceError as exc:
        raise HTTPException(502,f"Bengali OCR service failed: {exc}")
    except Exception as exc:
        # 422 is reserved for malformed client input. Unexpected parser failures
        # are server errors and must be visible as such in monitoring/logs.
        import logging
        logging.getLogger(__name__).exception("PDF preview extraction failed")
        raise HTTPException(
            500,
            "PDF extraction failed unexpectedly. Check the backend logs for the request details, then retry.",
        ) from exc


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
        chapter=data.chapter, set_name=data.set_name, paper=data.paper, declared_question_count=data.declared_question_count, source_file_name=data.source_file_name,
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
    raw=await file.read(settings.max_pdf_upload_mb*1024*1024+1)
    if len(raw)>settings.max_pdf_upload_mb*1024*1024: raise HTTPException(413,"File too large")
    try:
        doc=fitz.open(stream=raw,filetype="pdf"); pages=[p.get_text("text") for p in doc]
    except Exception: raise HTTPException(400,"Could not read PDF")
    text="\n".join(pages)
    return {"filename":file.filename,"kind":kind,"pages":len(pages),"extracted_text":text[:100000],"message":"Text preview only. For exam creation use /imports/pdf/preview, review the extracted metadata/questions, then /imports/pdf/create-exam."}

@router.get("/health")
def health(): return {"status":"ok","service":"exam-platform-api"}

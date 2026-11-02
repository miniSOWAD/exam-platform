import enum, uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Integer, Float, Text, JSON, Enum, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

def uid(): return str(uuid.uuid4())
def now(): return datetime.now(timezone.utc)

class Role(str, enum.Enum):
    admin="admin"; moderator="moderator"; student="student"
class ExamStatus(str, enum.Enum):
    draft="draft"; published="published"; live="live"; paused="paused"; ended="ended"; results_published="results_published"; archived="archived"
class User(Base):
    __tablename__="users"
    id: Mapped[str]=mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str]=mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str]=mapped_column(String(160))
    password_hash: Mapped[str]=mapped_column(String(255))
    role: Mapped[Role]=mapped_column(Enum(Role), default=Role.student, index=True)
    active: Mapped[bool]=mapped_column(Boolean, default=True)
    avatar_url: Mapped[str|None]=mapped_column(String(1200), nullable=True)
    avatar_public_id: Mapped[str|None]=mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=now)

Index("uq_single_admin_role", User.role, unique=True, postgresql_where=(User.role == Role.admin), sqlite_where=(User.role == Role.admin))

class PermissionGrant(Base):
    __tablename__="permission_grants"
    id: Mapped[str]=mapped_column(String(36), primary_key=True, default=uid)
    moderator_id: Mapped[str]=mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    code: Mapped[str]=mapped_column(String(80), index=True)
    granted_by: Mapped[str]=mapped_column(ForeignKey("users.id"))
    active: Mapped[bool]=mapped_column(Boolean, default=True)
    __table_args__=(UniqueConstraint("moderator_id","code"),)

class Exam(Base):
    __tablename__="exams"
    id: Mapped[str]=mapped_column(String(36), primary_key=True, default=uid)
    title: Mapped[str]=mapped_column(String(220), index=True)
    description: Mapped[str]=mapped_column(Text, default="")
    subject: Mapped[str]=mapped_column(String(100), default="General")
    chapter: Mapped[str|None]=mapped_column(String(220), nullable=True)
    set_name: Mapped[str|None]=mapped_column(String(100), nullable=True)
    declared_question_count: Mapped[int|None]=mapped_column(Integer, nullable=True)
    source_file_name: Mapped[str|None]=mapped_column(String(255), nullable=True)
    status: Mapped[ExamStatus]=mapped_column(Enum(ExamStatus), default=ExamStatus.draft, index=True)
    access_mode: Mapped[str]=mapped_column(String(30), default="all_students")
    duration_seconds: Mapped[int]=mapped_column(Integer, default=3600)
    max_attempts: Mapped[int]=mapped_column(Integer, default=1)
    pass_marks: Mapped[float]=mapped_column(Float, default=0)
    started_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True), nullable=True)
    paused_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True), nullable=True)
    accumulated_pause_seconds: Mapped[int]=mapped_column(Integer, default=0)
    ended_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_start_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True), nullable=True, index=True)
    scheduled_end_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True), nullable=True)
    time_extension_seconds: Mapped[int]=mapped_column(Integer, default=0)
    created_by: Mapped[str]=mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=now)
    questions: Mapped[list["Question"]]=relationship(back_populates="exam", cascade="all, delete-orphan")

class Question(Base):
    __tablename__="questions"
    id: Mapped[str]=mapped_column(String(36), primary_key=True, default=uid)
    exam_id: Mapped[str]=mapped_column(ForeignKey("exams.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str]=mapped_column(String(30), default="mcq")
    prompt: Mapped[str]=mapped_column(Text)
    options: Mapped[list]=mapped_column(JSON, default=list)
    answer_key: Mapped[dict]=mapped_column(JSON, default=dict)
    marks: Mapped[float]=mapped_column(Float, default=1)
    negative_marks: Mapped[float]=mapped_column(Float, default=0)
    position: Mapped[int]=mapped_column(Integer, default=0)
    exam: Mapped[Exam]=relationship(back_populates="questions")

class AccessGrant(Base):
    __tablename__="exam_access_grants"
    id: Mapped[str]=mapped_column(String(36), primary_key=True, default=uid)
    exam_id: Mapped[str]=mapped_column(ForeignKey("exams.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[str]=mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    active: Mapped[bool]=mapped_column(Boolean, default=True)
    __table_args__=(UniqueConstraint("exam_id","student_id"),)

class Attempt(Base):
    __tablename__="attempts"
    id: Mapped[str]=mapped_column(String(36), primary_key=True, default=uid)
    exam_id: Mapped[str]=mapped_column(ForeignKey("exams.id"), index=True)
    student_id: Mapped[str]=mapped_column(ForeignKey("users.id"), index=True)
    attempt_number: Mapped[int]=mapped_column(Integer, default=1)
    status: Mapped[str]=mapped_column(String(30), default="in_progress", index=True)
    started_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=now)
    submitted_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True), nullable=True)
    score: Mapped[float|None]=mapped_column(Float, nullable=True)
    max_score: Mapped[float]=mapped_column(Float, default=0)
    answers: Mapped[list]=mapped_column(JSON, default=list)
    __table_args__=(UniqueConstraint("exam_id","student_id","attempt_number"),)

class HistoricalResult(Base):
    __tablename__="historical_results"
    id: Mapped[str]=mapped_column(String(36), primary_key=True, default=uid)
    student_name: Mapped[str]=mapped_column(String(160))
    student_code: Mapped[str]=mapped_column(String(100), default="")
    exam_title: Mapped[str]=mapped_column(String(220))
    score: Mapped[float]=mapped_column(Float)
    max_score: Mapped[float]=mapped_column(Float)
    imported_by: Mapped[str]=mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=now)


class SiteContent(Base):
    __tablename__="site_content"
    id: Mapped[str]=mapped_column(String(40), primary_key=True, default="global")
    brand_name: Mapped[str]=mapped_column(String(100), default="ExamFlow")
    ribbon_text: Mapped[str]=mapped_column(String(180), default="A calmer space for focused exam preparation")
    ribbon_right_text: Mapped[str]=mapped_column(String(180), default="Mathematics · Physics · Chemistry · Biology")
    hero_eyebrow: Mapped[str]=mapped_column(String(180), default="EXAMINATION PREPARATION, REIMAGINED")
    hero_title: Mapped[str]=mapped_column(String(180), default="Prepare with purpose.")
    hero_highlight: Mapped[str]=mapped_column(String(180), default="Perform with confidence.")
    hero_description: Mapped[str]=mapped_column(Text, default="A thoughtful workspace for creating exams, practicing what matters and understanding every result across Mathematics, Physics, Chemistry and Biology.")
    hero_primary_cta: Mapped[str]=mapped_column(String(80), default="Create student account")
    hero_secondary_cta: Mapped[str]=mapped_column(String(80), default="Sign in")
    upcoming_title: Mapped[str]=mapped_column(String(180), default="Live & upcoming exams")
    upcoming_subtitle: Mapped[str]=mapped_column(String(300), default="Find an assessment and check your preparation.")
    calendar_title: Mapped[str]=mapped_column(String(180), default="University exam calendar")
    calendar_subtitle: Mapped[str]=mapped_column(String(300), default="Keep your academic schedule in view and make room for consistent practice.")
    leaderboard_title: Mapped[str]=mapped_column(String(180), default="Leaderboard")
    leaderboard_subtitle: Mapped[str]=mapped_column(String(300), default="See how students performed in published examinations.")
    features_title: Mapped[str]=mapped_column(String(180), default="Tools for the full examination journey.")
    features_subtitle: Mapped[str]=mapped_column(String(500), default="From the first question to the final result, keep every part of your learning and assessment workflow connected.")
    owner_profile_kicker: Mapped[str]=mapped_column(String(100), default="SITE OWNER")
    owner_expertise_heading: Mapped[str]=mapped_column(String(180), default="Areas of expertise")
    owner_name: Mapped[str]=mapped_column(String(160), default="Md Mahruf Alam")
    owner_role: Mapped[str]=mapped_column(String(180), default="Site Owner · Tutor & Examiner")
    owner_bio: Mapped[str]=mapped_column(Text, default="I am Md Mahruf Alam, the owner of ExamFlow. I help learners prepare through structured examinations, tutoring and clear performance feedback.")
    owner_education: Mapped[str]=mapped_column(String(220), default="")
    owner_institution: Mapped[str]=mapped_column(String(220), default="")
    owner_expertise: Mapped[list]=mapped_column(JSON, default=lambda: ["Mathematics", "Physics", "Chemistry", "Biology"])
    owner_avatar_url: Mapped[str]=mapped_column(String(1000), default="")
    owner_email: Mapped[str]=mapped_column(String(255), default="")
    owner_phone: Mapped[str]=mapped_column(String(60), default="")
    owner_website: Mapped[str]=mapped_column(String(1000), default="")
    owner_social_links: Mapped[dict]=mapped_column(JSON, default=dict)
    subjects: Mapped[list]=mapped_column(JSON, default=lambda: ["Mathematics", "Physics", "Chemistry", "Biology"])
    feature_cards: Mapped[list]=mapped_column(JSON, default=lambda: [
        {"label":"Exam builder","title":"Build better assessments","description":"Create question sets, configure marks and organize exams by subject, chapter and set."},
        {"label":"Live control","title":"Manage live examinations","description":"Start, pause and resume exams with a server-controlled timer and reliable answer saving."},
        {"label":"Performance","title":"Understand every result","description":"Review scores, compare published rankings and follow performance across attempts."}
    ])
    footer_text: Mapped[str]=mapped_column(String(240), default="Built for focused learning and fair assessment.")
    updated_by: Mapped[str|None]=mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=now, onupdate=now)

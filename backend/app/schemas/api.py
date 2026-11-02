from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Literal, Any
from datetime import datetime

class RegisterIn(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=10, max_length=128)
class LoginIn(BaseModel):
    email: EmailStr
    password: str
class UserOut(BaseModel):
    id: str; email: EmailStr; full_name: str; role: str; avatar_url: str | None = None
    model_config=ConfigDict(from_attributes=True)
class QuestionIn(BaseModel):
    kind: Literal["mcq","multiple_mcq","true_false","short_answer"]
    prompt: str = Field(min_length=1)
    options: list[dict[str,Any]] = Field(default_factory=list)
    answer_key: dict[str,Any] = Field(default_factory=dict)
    marks: float = Field(default=1, ge=0)
    negative_marks: float = Field(default=0, ge=0)
    position: int = 0
class ExamIn(BaseModel):
    title: str = Field(min_length=3, max_length=220)
    description: str = ""
    subject: str = "General"
    chapter: str | None = None
    set_name: str | None = None
    declared_question_count: int | None = Field(default=None, ge=0, le=10000)
    source_file_name: str | None = Field(default=None, max_length=255)
    duration_seconds: int = Field(default=3600, ge=60, le=86400)
    max_attempts: int = Field(default=1, ge=1, le=20)
    pass_marks: float = Field(default=0, ge=0)
    access_mode: Literal["all_students","selected_students"] = "all_students"
    scheduled_start_at: datetime | None = None
    scheduled_end_at: datetime | None = None
class AnswerIn(BaseModel):
    answer: dict[str,Any]
class GrantIn(BaseModel):
    student_id: str
class PermissionIn(BaseModel):
    codes: list[str]


class ImportedQuestionIn(BaseModel):
    number: int = Field(ge=1)
    kind: Literal["mcq", "multiple_mcq", "true_false", "short_answer"] = "mcq"
    prompt: str = Field(min_length=1, max_length=12000)
    options: list[dict[str, Any]] = Field(default_factory=list)
    answer_key: dict[str, Any] = Field(default_factory=dict)
    marks: float = Field(default=1, ge=0)
    negative_marks: float = Field(default=0, ge=0)

class PDFCreateExamIn(BaseModel):
    title: str = Field(min_length=3, max_length=220)
    subject: str = Field(default="General", max_length=100)
    chapter: str | None = Field(default=None, max_length=220)
    set_name: str | None = Field(default=None, max_length=100)
    duration_minutes: int = Field(default=60, ge=1, le=1440)
    declared_question_count: int | None = Field(default=None, ge=0, le=10000)
    questions: list[ImportedQuestionIn] = Field(min_length=1, max_length=1000)
    access_mode: Literal["all_students", "selected_students"] = "all_students"
    max_attempts: int = Field(default=1, ge=1, le=20)
    publish_immediately: bool = False
    source_file_name: str | None = Field(default=None, max_length=255)


class SiteContentUpdate(BaseModel):
    brand_name: str | None = Field(default=None, min_length=2, max_length=100)
    ribbon_text: str | None = Field(default=None, max_length=180)
    ribbon_right_text: str | None = Field(default=None, max_length=180)
    hero_eyebrow: str | None = Field(default=None, max_length=180)
    hero_title: str | None = Field(default=None, max_length=180)
    hero_highlight: str | None = Field(default=None, max_length=180)
    hero_description: str | None = Field(default=None, max_length=3000)
    hero_primary_cta: str | None = Field(default=None, max_length=80)
    hero_secondary_cta: str | None = Field(default=None, max_length=80)
    upcoming_title: str | None = Field(default=None, max_length=180)
    upcoming_subtitle: str | None = Field(default=None, max_length=300)
    calendar_title: str | None = Field(default=None, max_length=180)
    calendar_subtitle: str | None = Field(default=None, max_length=300)
    leaderboard_title: str | None = Field(default=None, max_length=180)
    leaderboard_subtitle: str | None = Field(default=None, max_length=300)
    features_title: str | None = Field(default=None, max_length=180)
    features_subtitle: str | None = Field(default=None, max_length=500)
    owner_profile_kicker: str | None = Field(default=None, max_length=100)
    owner_expertise_heading: str | None = Field(default=None, max_length=180)
    owner_name: str | None = Field(default=None, min_length=2, max_length=160)
    owner_role: str | None = Field(default=None, max_length=180)
    owner_bio: str | None = Field(default=None, max_length=5000)
    owner_education: str | None = Field(default=None, max_length=220)
    owner_institution: str | None = Field(default=None, max_length=220)
    owner_expertise: list[str] | None = None
    owner_avatar_url: str | None = Field(default=None, max_length=1000)
    owner_email: str | None = Field(default=None, max_length=255)
    owner_phone: str | None = Field(default=None, max_length=60)
    owner_website: str | None = Field(default=None, max_length=1000)
    owner_social_links: dict[str, str] | None = None
    subjects: list[str] | None = None
    feature_cards: list[dict[str, Any]] | None = None
    footer_text: str | None = Field(default=None, max_length=240)

class ScheduleUpdate(BaseModel):
    scheduled_start_at: datetime | None = None
    scheduled_end_at: datetime | None = None

class ExtendTimeIn(BaseModel):
    minutes: int = Field(ge=1, le=1440)

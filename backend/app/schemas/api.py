from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Literal, Any

class RegisterIn(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=10, max_length=128)
class LoginIn(BaseModel):
    email: EmailStr
    password: str
class UserOut(BaseModel):
    id: str; email: EmailStr; full_name: str; role: str
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

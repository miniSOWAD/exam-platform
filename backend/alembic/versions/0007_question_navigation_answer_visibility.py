"""Add persistent question navigation and answer-sheet visibility controls.

Revision ID: 0007_question_navigation_answer_visibility
Revises: 0006_admin_exam_mode
Create Date: 2026-11-13
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_question_navigation_answer_visibility"
down_revision = "0006_admin_exam_mode"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    exam_columns = {column["name"] for column in sa.inspect(bind).get_columns("exams")}
    if "answers_public" not in exam_columns:
        op.add_column("exams", sa.Column("answers_public", sa.Boolean(), nullable=False, server_default=sa.false()))
        op.alter_column("exams", "answers_public", server_default=None)
    if "hide_participant_answers" not in exam_columns:
        op.add_column("exams", sa.Column("hide_participant_answers", sa.Boolean(), nullable=False, server_default=sa.false()))
        op.alter_column("exams", "hide_participant_answers", server_default=None)

    attempt_columns = {column["name"] for column in sa.inspect(bind).get_columns("attempts")}
    if "is_staff_attempt" not in attempt_columns:
        op.add_column("attempts", sa.Column("is_staff_attempt", sa.Boolean(), nullable=False, server_default=sa.false()))
        op.alter_column("attempts", "is_staff_attempt", server_default=None)
    if "visited_question_ids" not in attempt_columns:
        op.add_column(
            "attempts",
            sa.Column("visited_question_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        )
        op.alter_column("attempts", "visited_question_ids", server_default=None)

    if not sa.inspect(bind).has_table("answer_visibility_grants"):
        op.create_table(
            "answer_visibility_grants",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("exam_id", sa.String(length=36), sa.ForeignKey("exams.id", ondelete="CASCADE"), nullable=False),
            sa.Column("student_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("granted_by", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("exam_id", "student_id", name="uq_answer_visibility_exam_student"),
        )
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("answer_visibility_grants")}
    if "ix_answer_visibility_grants_exam_id" not in indexes:
        op.create_index("ix_answer_visibility_grants_exam_id", "answer_visibility_grants", ["exam_id"], unique=False)
    if "ix_answer_visibility_grants_student_id" not in indexes:
        op.create_index("ix_answer_visibility_grants_student_id", "answer_visibility_grants", ["student_id"], unique=False)


def downgrade():
    bind = op.get_bind()
    if sa.inspect(bind).has_table("answer_visibility_grants"):
        op.drop_table("answer_visibility_grants")
    attempt_columns = {column["name"] for column in sa.inspect(bind).get_columns("attempts")}
    if "visited_question_ids" in attempt_columns:
        op.drop_column("attempts", "visited_question_ids")
    if "is_staff_attempt" in attempt_columns:
        op.drop_column("attempts", "is_staff_attempt")
    exam_columns = {column["name"] for column in sa.inspect(bind).get_columns("exams")}
    if "hide_participant_answers" in exam_columns:
        op.drop_column("exams", "hide_participant_answers")
    if "answers_public" in exam_columns:
        op.drop_column("exams", "answers_public")

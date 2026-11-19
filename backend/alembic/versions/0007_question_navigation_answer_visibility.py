"""Add persistent question navigation and answer-sheet visibility controls.

Revision ID: 0007_qnav_visibility
Revises: 0006_admin_exam_mode
Create Date: 2026-11-13

PostgreSQL-safe and retry-safe: retain server defaults on newly-added columns
so existing rows can be backfilled without a follow-up ALTER COLUMN.
"""
from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa

revision = "0007_qnav_visibility"
down_revision = "0006_admin_exam_mode"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration")


def _columns(bind, table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def upgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name
    logger.info("0007: ensuring exam answer-visibility columns (dialect=%s)", dialect)

    exam_columns = _columns(bind, "exams")
    if "answers_public" not in exam_columns:
        op.add_column(
            "exams",
            sa.Column("answers_public", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if "hide_participant_answers" not in exam_columns:
        op.add_column(
            "exams",
            sa.Column("hide_participant_answers", sa.Boolean(), nullable=False, server_default=sa.false()),
        )

    logger.info("0007: ensuring attempt navigation columns")
    attempt_columns = _columns(bind, "attempts")
    if "is_staff_attempt" not in attempt_columns:
        op.add_column(
            "attempts",
            sa.Column("is_staff_attempt", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if "visited_question_ids" not in attempt_columns:
        # PostgreSQL needs an explicitly typed JSON default; SQLite accepts the
        # plain string literal. Keep the default to support any older writers.
        json_default = sa.text("'[]'::json") if dialect == "postgresql" else sa.text("'[]'")
        op.add_column(
            "attempts",
            sa.Column("visited_question_ids", sa.JSON(), nullable=False, server_default=json_default),
        )

    logger.info("0007: ensuring answer_visibility_grants table")
    inspector = sa.inspect(bind)
    if not inspector.has_table("answer_visibility_grants"):
        op.create_table(
            "answer_visibility_grants",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("exam_id", sa.String(length=36), sa.ForeignKey("exams.id", ondelete="CASCADE"), nullable=False),
            sa.Column("student_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("granted_by", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("exam_id", "student_id", name="uq_answer_visibility_exam_student"),
        )

    logger.info("0007: ensuring answer_visibility_grants indexes")
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("answer_visibility_grants")}
    if "ix_answer_visibility_grants_exam_id" not in indexes:
        op.create_index("ix_answer_visibility_grants_exam_id", "answer_visibility_grants", ["exam_id"], unique=False)
    if "ix_answer_visibility_grants_student_id" not in indexes:
        op.create_index("ix_answer_visibility_grants_student_id", "answer_visibility_grants", ["student_id"], unique=False)

    logger.info("0007: question navigation and answer visibility schema is ready")


def downgrade():
    bind = op.get_bind()
    if sa.inspect(bind).has_table("answer_visibility_grants"):
        op.drop_table("answer_visibility_grants")
    attempt_columns = _columns(bind, "attempts")
    if "visited_question_ids" in attempt_columns:
        op.drop_column("attempts", "visited_question_ids")
    if "is_staff_attempt" in attempt_columns:
        op.drop_column("attempts", "is_staff_attempt")
    exam_columns = _columns(bind, "exams")
    if "hide_participant_answers" in exam_columns:
        op.drop_column("exams", "hide_participant_answers")
    if "answers_public" in exam_columns:
        op.drop_column("exams", "answers_public")

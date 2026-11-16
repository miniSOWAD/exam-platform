"""Add administrator preview attempts and scheduled exam resume.

Revision ID: 0006_admin_exam_mode
Revises: 0005_admin_control_center
Create Date: 2026-11-13
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_admin_exam_mode"
down_revision = "0005_admin_control_center"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    exam_columns = {column["name"] for column in sa.inspect(bind).get_columns("exams")}
    if "scheduled_resume_at" not in exam_columns:
        op.add_column("exams", sa.Column("scheduled_resume_at", sa.DateTime(timezone=True), nullable=True))

    attempt_columns = {column["name"] for column in sa.inspect(bind).get_columns("attempts")}
    if "is_admin_attempt" not in attempt_columns:
        op.add_column(
            "attempts",
            sa.Column("is_admin_attempt", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        op.alter_column("attempts", "is_admin_attempt", server_default=None)


def downgrade():
    bind = op.get_bind()
    attempt_columns = {column["name"] for column in sa.inspect(bind).get_columns("attempts")}
    if "is_admin_attempt" in attempt_columns:
        op.drop_column("attempts", "is_admin_attempt")
    exam_columns = {column["name"] for column in sa.inspect(bind).get_columns("exams")}
    if "scheduled_resume_at" in exam_columns:
        op.drop_column("exams", "scheduled_resume_at")

"""Track separate sittings when an administrator restarts an ended exam.

Revision ID: 0008_admin_restart_runs
Revises: 0007_qnav_visibility
Create Date: 2026-11-16

Keep a database default of 1 so pre-existing exams and attempts are backfilled
atomically on PostgreSQL without a second ALTER COLUMN operation.
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_admin_restart_runs"
down_revision = "0007_qnav_visibility"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    exam_columns = {column["name"] for column in sa.inspect(bind).get_columns("exams")}
    if "run_number" not in exam_columns:
        op.add_column("exams", sa.Column("run_number", sa.Integer(), nullable=False, server_default=sa.text("1")))

    attempt_columns = {column["name"] for column in sa.inspect(bind).get_columns("attempts")}
    if "run_number" not in attempt_columns:
        op.add_column("attempts", sa.Column("run_number", sa.Integer(), nullable=False, server_default=sa.text("1")))


def downgrade():
    bind = op.get_bind()
    attempt_columns = {column["name"] for column in sa.inspect(bind).get_columns("attempts")}
    if "run_number" in attempt_columns:
        op.drop_column("attempts", "run_number")
    exam_columns = {column["name"] for column in sa.inspect(bind).get_columns("exams")}
    if "run_number" in exam_columns:
        op.drop_column("exams", "run_number")

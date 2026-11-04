"""Add admin control-center metadata and managed leaderboard records."""
from alembic import op
import sqlalchemy as sa

revision = "0005_admin_control_center"
down_revision = ("0004_attempt_pause_baseline", "0004_user_avatars_cloudinary")
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    exam_columns = {column["name"] for column in sa.inspect(bind).get_columns("exams")}
    if "paper" not in exam_columns:
        op.add_column("exams", sa.Column("paper", sa.String(length=40), nullable=True))
    exam_indexes = {index["name"] for index in sa.inspect(bind).get_indexes("exams")}
    if "ix_exams_paper" not in exam_indexes:
        op.create_index("ix_exams_paper", "exams", ["paper"], unique=False)

    if not sa.inspect(bind).has_table("leaderboard_entries"):
        op.create_table(
            "leaderboard_entries",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("scope", sa.String(length=20), nullable=False),
            sa.Column("display_name", sa.String(length=160), nullable=False),
            sa.Column("student_identifier", sa.String(length=255), nullable=True),
            sa.Column("student_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("exam_id", sa.String(length=36), sa.ForeignKey("exams.id", ondelete="SET NULL"), nullable=True),
            sa.Column("paper", sa.String(length=40), nullable=True),
            sa.Column("subject", sa.String(length=100), nullable=True),
            sa.Column("score", sa.Float(), nullable=False),
            sa.Column("max_score", sa.Float(), nullable=True),
            sa.Column("created_by", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
    entry_indexes = {index["name"] for index in sa.inspect(bind).get_indexes("leaderboard_entries")}
    for name, columns in [
        ("ix_leaderboard_entries_scope", ["scope"]),
        ("ix_leaderboard_entries_student_id", ["student_id"]),
        ("ix_leaderboard_entries_exam_id", ["exam_id"]),
        ("ix_leaderboard_entries_paper", ["paper"]),
        ("ix_leaderboard_entries_subject", ["subject"]),
    ]:
        if name not in entry_indexes:
            op.create_index(name, "leaderboard_entries", columns, unique=False)

    if not sa.inspect(bind).has_table("leaderboard_exclusions"):
        op.create_table(
            "leaderboard_exclusions",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("scope", sa.String(length=20), nullable=False),
            sa.Column("student_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("exam_id", sa.String(length=36), sa.ForeignKey("exams.id", ondelete="CASCADE"), nullable=True),
            sa.Column("paper", sa.String(length=40), nullable=True),
            sa.Column("subject", sa.String(length=100), nullable=True),
            sa.Column("created_by", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
    exclusion_indexes = {index["name"] for index in sa.inspect(bind).get_indexes("leaderboard_exclusions")}
    for name, columns in [
        ("ix_leaderboard_exclusions_scope", ["scope"]),
        ("ix_leaderboard_exclusions_student_id", ["student_id"]),
        ("ix_leaderboard_exclusions_exam_id", ["exam_id"]),
        ("ix_leaderboard_exclusions_paper", ["paper"]),
        ("ix_leaderboard_exclusions_subject", ["subject"]),
    ]:
        if name not in exclusion_indexes:
            op.create_index(name, "leaderboard_exclusions", columns, unique=False)


def downgrade():
    bind = op.get_bind()
    if sa.inspect(bind).has_table("leaderboard_exclusions"):
        op.drop_table("leaderboard_exclusions")
    if sa.inspect(bind).has_table("leaderboard_entries"):
        op.drop_table("leaderboard_entries")
    columns = {column["name"] for column in sa.inspect(bind).get_columns("exams")}
    if "paper" in columns:
        indexes = {index["name"] for index in sa.inspect(bind).get_indexes("exams")}
        if "ix_exams_paper" in indexes:
            op.drop_index("ix_exams_paper", table_name="exams")
        op.drop_column("exams", "paper")

"""Add editable public site profile and examination scheduling fields."""
from alembic import op
import sqlalchemy as sa

revision = "0003_site_profile_exam_schedule"
down_revision = "0002_exam_pdf_metadata"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    existing = {c["name"] for c in sa.inspect(bind).get_columns("exams")}
    if "scheduled_start_at" not in existing:
        op.add_column("exams", sa.Column("scheduled_start_at", sa.DateTime(timezone=True), nullable=True))
    if "scheduled_end_at" not in existing:
        op.add_column("exams", sa.Column("scheduled_end_at", sa.DateTime(timezone=True), nullable=True))
    if "site_profile" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "site_profile",
            sa.Column("id", sa.String(length=20), primary_key=True),
            sa.Column("owner_name", sa.String(length=160), nullable=False, server_default="Md Mahruf Alam"),
            sa.Column("owner_role", sa.String(length=220), nullable=False, server_default="Owner · Tutor · Examiner"),
            sa.Column("owner_bio", sa.Text(), nullable=False, server_default="I created ExamFlow to make exam preparation, assessment and performance tracking more organized and accessible."),
            sa.Column("owner_education", sa.String(length=220), nullable=False, server_default=""),
            sa.Column("owner_department", sa.String(length=220), nullable=False, server_default=""),
            sa.Column("owner_institution", sa.String(length=220), nullable=False, server_default=""),
            sa.Column("owner_location", sa.String(length=160), nullable=False, server_default=""),
            sa.Column("owner_photo_url", sa.String(length=1000), nullable=False, server_default=""),
            sa.Column("owner_email", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("owner_social_links", sa.JSON(), nullable=False),
            sa.Column("announcement", sa.String(length=300), nullable=False, server_default="A calmer space for focused exam preparation"),
            sa.Column("hero_eyebrow", sa.String(length=160), nullable=False, server_default="EXAMINATION PREPARATION, REIMAGINED"),
            sa.Column("hero_title", sa.String(length=220), nullable=False, server_default="Prepare with purpose."),
            sa.Column("hero_highlight", sa.String(length=220), nullable=False, server_default="Perform with confidence."),
            sa.Column("hero_description", sa.Text(), nullable=False, server_default="A thoughtful workspace for creating exams, practicing what matters and understanding every result across Mathematics, Physics, Chemistry and Biology."),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )


def downgrade():
    op.drop_table("site_profile")
    op.drop_column("exams", "scheduled_end_at")
    op.drop_column("exams", "scheduled_start_at")

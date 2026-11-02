"""Add editable public owner/site content and exam scheduling controls."""
from alembic import op
import sqlalchemy as sa

revision = "0003_owner_content_schedule"
down_revision = "0002_exam_pdf_metadata"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    existing = {column["name"] for column in sa.inspect(bind).get_columns("exams")}
    additions = [
        ("scheduled_start_at", sa.DateTime(timezone=True)),
        ("scheduled_end_at", sa.DateTime(timezone=True)),
        ("time_extension_seconds", sa.Integer()),
    ]
    for name, column_type in additions:
        if name not in existing:
            op.add_column("exams", sa.Column(name, column_type, nullable=True if name != "time_extension_seconds" else False, server_default="0" if name == "time_extension_seconds" else None))
    index_names = {index["name"] for index in sa.inspect(bind).get_indexes("exams")}
    if "ix_exams_scheduled_start_at" not in index_names:
        op.create_index("ix_exams_scheduled_start_at", "exams", ["scheduled_start_at"], unique=False)
    if not sa.inspect(bind).has_table("site_content"):
        op.create_table(
            "site_content",
            sa.Column("id", sa.String(length=40), primary_key=True),
            sa.Column("brand_name", sa.String(length=100), nullable=False),
            sa.Column("ribbon_text", sa.String(length=180), nullable=False),
            sa.Column("ribbon_right_text", sa.String(length=180), nullable=False),
            sa.Column("hero_eyebrow", sa.String(length=180), nullable=False),
            sa.Column("hero_title", sa.String(length=180), nullable=False),
            sa.Column("hero_highlight", sa.String(length=180), nullable=False),
            sa.Column("hero_description", sa.Text(), nullable=False),
            sa.Column("hero_primary_cta", sa.String(length=80), nullable=False),
            sa.Column("hero_secondary_cta", sa.String(length=80), nullable=False),
            sa.Column("upcoming_title", sa.String(length=180), nullable=False),
            sa.Column("upcoming_subtitle", sa.String(length=300), nullable=False),
            sa.Column("calendar_title", sa.String(length=180), nullable=False),
            sa.Column("calendar_subtitle", sa.String(length=300), nullable=False),
            sa.Column("leaderboard_title", sa.String(length=180), nullable=False),
            sa.Column("leaderboard_subtitle", sa.String(length=300), nullable=False),
            sa.Column("features_title", sa.String(length=180), nullable=False),
            sa.Column("features_subtitle", sa.String(length=500), nullable=False),
            sa.Column("owner_profile_kicker", sa.String(length=100), nullable=False),
            sa.Column("owner_expertise_heading", sa.String(length=180), nullable=False),
            sa.Column("owner_name", sa.String(length=160), nullable=False),
            sa.Column("owner_role", sa.String(length=180), nullable=False),
            sa.Column("owner_bio", sa.Text(), nullable=False),
            sa.Column("owner_education", sa.String(length=220), nullable=False),
            sa.Column("owner_institution", sa.String(length=220), nullable=False),
            sa.Column("owner_expertise", sa.JSON(), nullable=False),
            sa.Column("owner_avatar_url", sa.String(length=1000), nullable=False),
            sa.Column("owner_email", sa.String(length=255), nullable=False),
            sa.Column("owner_phone", sa.String(length=60), nullable=False),
            sa.Column("owner_website", sa.String(length=1000), nullable=False),
            sa.Column("owner_social_links", sa.JSON(), nullable=False),
            sa.Column("subjects", sa.JSON(), nullable=False),
            sa.Column("feature_cards", sa.JSON(), nullable=False),
            sa.Column("footer_text", sa.String(length=240), nullable=False),
            sa.Column("updated_by", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
    else:
        site_columns = {column["name"] for column in sa.inspect(bind).get_columns("site_content")}
        site_additions = [
            ("hero_primary_cta", sa.String(length=80), "Create student account"),
            ("hero_secondary_cta", sa.String(length=80), "Sign in"),
            ("upcoming_title", sa.String(length=180), "Live & upcoming exams"),
            ("upcoming_subtitle", sa.String(length=300), "Find an assessment and check your preparation."),
            ("calendar_title", sa.String(length=180), "University exam calendar"),
            ("calendar_subtitle", sa.String(length=300), "Keep your academic schedule in view and make room for consistent practice."),
            ("leaderboard_title", sa.String(length=180), "Leaderboard"),
            ("leaderboard_subtitle", sa.String(length=300), "See how students performed in published examinations."),
            ("features_title", sa.String(length=180), "Tools for the full examination journey."),
            ("features_subtitle", sa.String(length=500), "From the first question to the final result, keep every part of your learning and assessment workflow connected."),
            ("owner_profile_kicker", sa.String(length=100), "SITE OWNER"),
            ("owner_expertise_heading", sa.String(length=180), "Areas of expertise"),
            ("owner_phone", sa.String(length=60), ""),
        ]
        for name, column_type, default_value in site_additions:
            if name not in site_columns:
                op.add_column("site_content", sa.Column(name, column_type, nullable=False, server_default=default_value))


def downgrade():
    op.drop_table("site_content")
    op.drop_index("ix_exams_scheduled_start_at", table_name="exams")
    op.drop_column("exams", "time_extension_seconds")
    op.drop_column("exams", "scheduled_end_at")
    op.drop_column("exams", "scheduled_start_at")

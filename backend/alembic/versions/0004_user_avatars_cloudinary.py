"""Add Cloudinary-backed profile image references to users."""
from alembic import op
import sqlalchemy as sa

revision = "0004_user_avatars_cloudinary"
down_revision = "0003_owner_content_schedule"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("users")}
    if "avatar_url" not in columns:
        op.add_column("users", sa.Column("avatar_url", sa.String(length=1200), nullable=True))
    if "avatar_public_id" not in columns:
        op.add_column("users", sa.Column("avatar_public_id", sa.String(length=255), nullable=True))


def downgrade():
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("users")}
    if "avatar_public_id" in columns:
        op.drop_column("users", "avatar_public_id")
    if "avatar_url" in columns:
        op.drop_column("users", "avatar_url")

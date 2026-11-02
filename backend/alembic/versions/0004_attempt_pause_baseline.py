"""Track pause baseline per attempt so pre-attempt pauses do not extend student timers."""
from alembic import op
import sqlalchemy as sa

revision = "0004_attempt_pause_baseline"
down_revision = "0003_site_profile_exam_schedule"
branch_labels = None
depends_on = None

def upgrade():
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("attempts")}
    if "pause_seconds_at_start" not in existing:
        op.add_column("attempts", sa.Column("pause_seconds_at_start", sa.Integer(), nullable=False, server_default="0"))

def downgrade():
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("attempts")}
    if "pause_seconds_at_start" in existing:
        op.drop_column("attempts", "pause_seconds_at_start")

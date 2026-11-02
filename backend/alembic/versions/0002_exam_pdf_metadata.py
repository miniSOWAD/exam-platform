"""Add PDF-derived subject/chapter/set metadata to exams."""
from alembic import op
import sqlalchemy as sa

revision = "0002_exam_pdf_metadata"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("exams")}
    columns = [
        ("chapter", sa.String(length=220)),
        ("set_name", sa.String(length=100)),
        ("declared_question_count", sa.Integer()),
        ("source_file_name", sa.String(length=255)),
    ]
    for name, column_type in columns:
        if name not in existing:
            op.add_column("exams", sa.Column(name, column_type, nullable=True))


def downgrade():
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("exams")}
    for name in ("source_file_name", "declared_question_count", "set_name", "chapter"):
        if name in existing:
            op.drop_column("exams", name)

from pathlib import Path
import re

def test_alembic_revision_ids_fit_postgresql_default_version_column():
    versions = Path(__file__).resolve().parents[1] / "alembic" / "versions"
    ids = []
    for path in versions.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        match = re.search(r"^revision\s*=\s*['\"]([^'\"]+)", source, re.M)
        if match:
            ids.append((path.name, match.group(1)))
    assert ids, "No Alembic revision identifiers found"
    too_long = [(name, revision) for name, revision in ids if len(revision) > 32]
    assert not too_long, f"Alembic revision ids exceed PostgreSQL VARCHAR(32): {too_long}"

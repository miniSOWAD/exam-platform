import getpass

from app.core.config import settings
from app.core.database import SessionLocal, Base, engine
from app.core.security import hash_password
from app.models.entities import User, Role

Base.metadata.create_all(bind=engine)
db = SessionLocal()
try:
    if db.query(User).filter(User.role == Role.admin).count():
        raise SystemExit("An admin already exists.")
    email = (settings.admin_email or input("Admin email: ")).strip().lower()
    name = (settings.admin_name or input("Admin full name: ")).strip()
    password = settings.admin_password or getpass.getpass("Admin password (10+ chars): ")
    if len(password) < 10:
        raise SystemExit("Admin password must be at least 10 characters.")
    if not email or not name:
        raise SystemExit("Admin email and name are required.")
    db.add(User(email=email, full_name=name, password_hash=hash_password(password), role=Role.admin))
    db.commit()
    print("Admin created successfully.")
finally:
    db.close()

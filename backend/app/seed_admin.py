import getpass
from app.core.database import SessionLocal, Base, engine
from app.core.security import hash_password
from app.models.entities import User, Role
Base.metadata.create_all(bind=engine)
db=SessionLocal()
try:
    if db.query(User).filter(User.role==Role.admin).count(): raise SystemExit('An admin already exists.')
    email=input('Admin email: ').strip().lower(); name=input('Admin full name: ').strip(); password=getpass.getpass('Admin password (10+ chars): ')
    if len(password)<10: raise SystemExit('Password must be at least 10 characters.')
    db.add(User(email=email,full_name=name,password_hash=hash_password(password),role=Role.admin));db.commit();print('Admin created successfully.')
finally: db.close()

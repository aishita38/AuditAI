import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost:5433/postgres")

# Clean up accidental prefixes if the user pasted key name in value field
if DATABASE_URL.startswith("DATABASE_URL="):
    DATABASE_URL = DATABASE_URL.replace("DATABASE_URL=", "", 1)
elif DATABASE_URL.startswith("DATABASE_URL"):
    DATABASE_URL = DATABASE_URL.replace("DATABASE_URL", "", 1)

# Render provides postgres:// but SQLAlchemy requires postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Create engine. Connect args are not needed for postgres, but we can set pool size
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(DATABASE_URL, pool_size=10, max_overflow=20, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency to get db session in FastAPI endpoints
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

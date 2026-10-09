"""
SQLAlchemy engine + session setup, pointed at the Neon Postgres database
via DATABASE_URL (see config.py / .env.example).

Why SQLAlchemy here instead of raw psycopg2: the rest of the app (Pydantic
schemas, FastAPI dependency injection) already follows a "declare a model,
let the framework validate/serialize it" pattern -- the ORM keeps the auth
code in that same style instead of mixing in raw SQL strings.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import DATABASE_URL

# Neon (like most managed Postgres providers) requires SSL; `sslmode=require`
# is already part of the connection string you were given, so no extra
# connect_args are needed here.
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency -- yields a DB session per-request and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

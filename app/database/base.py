# app/database/base.py

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///data/money_tracker.db"

# Create a SQLAlchemy engine
engine = create_engine(DATABASE_URL, echo=False, future=True)

# Create a "Session" class
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

# Base class for all ORM models
Base = declarative_base()

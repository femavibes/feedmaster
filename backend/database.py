# backend/database.py
#
# This file sets up the SQLAlchemy database engine and session.
# It provides functions to get a database session and a base for declarative models.

import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# --- IMPORTANT: Import your models here to ensure they are registered with Base.metadata ---
# This line assumes your SQLAlchemy models are defined in 'backend/models.py'.
# If your models are in a different file (e.g., backend/schema.py or split across multiple files),
# adjust this import accordingly to ensure all your model classes are loaded.
# If you had multiple model files, you might do:
# from backend import user_models
# from backend import post_models
# etc.
# --- END IMPORTANT ---

# Load environment variables from .env file
load_dotenv()

# Retrieve the database URL from environment variables
# This URL should be in the format: postgresql://user:password@host:port/database_name
# Example: postgresql://user:password@db:5432/feedmaster_db
DATABASE_URL = os.getenv("DATABASE_URL")

# Create a SQLAlchemy engine
# connect_args={"check_same_thread": False} is needed for SQLite but generally not for PostgreSQL.
# However, it's often included in FastAPI examples. For PostgreSQL, it's safe to omit.
engine = create_engine(DATABASE_URL)

# Create a SessionLocal class
# Each instance of SessionLocal will be a database session.
# The expire_on_commit=False prevents objects from expiring after commit.
# This can be useful if you need to access attributes of objects after they've been committed,
# but be mindful of stale data if not refreshed.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Declare a Base for your SQLAlchemy models
# Models will inherit from this Base to become SQLAlchemy ORM models.
Base = declarative_base()

def get_db():
    """
    Dependency function to yield a database session.
    This is designed to be used with FastAPI's Depends system.
    It ensures the session is properly closed after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Note: The database connection will not be established until a session is actually requested.
# This lazy initialization is common in web applications.

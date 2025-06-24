import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Database connection string from environment variables
# Format: postgresql://user:password@host:port/dbname
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@db:5432/feedmaster_db")

# Create a SQLAlchemy engine
# pool_pre_ping=True helps with long-lived connections, useful in containerized environments
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# Create a SessionLocal class to get a database session
# Each instance of SessionLocal will be a database session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for our SQLAlchemy models
Base = declarative_base()

# Dependency to get a database session for each request in FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

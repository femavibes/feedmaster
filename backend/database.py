# backend/database.py
#
# This file sets up the SQLAlchemy database engine and session.
# It provides functions to get a database session and a base for declarative models.

import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession # Changed from create_engine
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
# You'll need to import your models here to ensure Base.metadata can find them.
# For example:
# from . import models

# Load environment variables from .env file
load_dotenv()

# Retrieve the database URL from environment variables
# This URL should be in the format: postgresql+asyncpg://user:password@host:port/database_name
# Note the 'asyncpg' driver for asynchronous operations.
DATABASE_URL = os.getenv("SQLALCHEMY_DATABASE_URL")

# Create an asynchronous SQLAlchemy engine
# pool_pre_ping=True helps maintain connection health
# pool_size and max_overflow can be tuned for your specific load
async_engine = create_async_engine(
    DATABASE_URL,
    echo=False, # Set to True to see SQL queries for debugging
    pool_pre_ping=True,
    pool_size=50, # Increased for better concurrent user handling
    max_overflow=50, # Max additional connections beyond pool_size
    pool_timeout=30, # Wait up to 30 seconds for a connection
    pool_recycle=3600 # Recycle connections every hour
)

# Create an asynchronous SessionLocal class
# Each instance of AsyncSessionLocal will be an asynchronous database session.
# The expire_on_commit=False prevents objects from expiring after commit.
# This can be useful if you need to access attributes of objects after they've been committed,
# but be mindful of stale data if not refreshed.
AsyncSessionLocal = sessionmaker(
    async_engine,
    class_=AsyncSession, # Use AsyncSession
    autocommit=False,
    autoflush=False,
    expire_on_commit=False
)

# Declare a Base for your SQLAlchemy models
# Models will inherit from this Base to become SQLAlchemy ORM models.
Base = declarative_base()

async def get_db():
    """
    Asynchronous dependency function to yield an asynchronous database session.
    This is designed to be used with FastAPI's Depends system.
    It ensures the session is properly closed after use.
    """
    db = AsyncSessionLocal()
    try:
        yield db
    finally:
        await db.close() # Await the close operation for async session

# Note: The database connection will not be established until a session is actually requested.
# This lazy initialization is common in web applications.

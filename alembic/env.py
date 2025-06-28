import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# This is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# --- START: Critical Alembic Configuration Changes ---

# Add your project's root to the Python path
# This is crucial so Alembic can import your 'backend' module
# This assumes env.py is in 'your_project_root/alembic/env.py'
# and your application code (e.g., database.py, models.py) is in 'your_project_root/backend/'
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# Import your SQLAlchemy Base (or SQLModel.metadata) here
# for 'autogenerate' support.
# Adjust the import path 'backend.database' if your Base/metadata is located elsewhere.
try:
    from backend.database import Base # This imports the Base object from your database setup

    # IMPORTANT: Import your models here to ensure they are registered with Base.metadata
    # This line assumes your SQLAlchemy models are defined in 'backend/models.py'.
    # If your models are in a different file (e.g., backend/schema.py or split across multiple files),
    # adjust this import accordingly to ensure all your model classes are loaded.
    from backend import models # <--- THIS IS THE CRITICAL ADDITION/UNCOMMENT!

    # Set target_metadata to your imported Base.metadata
    target_metadata = Base.metadata

    # Example for SQLModel (if you were using SQLModel directly instead of SQLAlchemy Base):
    # from backend.models import SQLModel
    # target_metadata = SQLModel.metadata # If using SQLModel directly

except ImportError as e:
    print(f"Error importing SQLAlchemy Base/metadata or models: {e}")
    print(f"Current sys.path: {sys.path}")
    print("Please ensure your 'backend' module is correctly structured and 'Base' (or 'SQLModel') is importable from 'alembic/env.py'.")
    sys.exit(1)

# --- END: Critical Alembic Configuration Changes ---

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well. By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    # Get the database URL from the DATABASE_URL environment variable
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise Exception("DATABASE_URL environment variable is not set. Alembic cannot connect to the database.")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Get the database URL from the DATABASE_URL environment variable
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise Exception("DATABASE_URL environment variable is not set. Alembic cannot connect to the database.")

    # Create a connectable using the database URL
    connectable = engine_from_config(
        {"sqlalchemy.url": url}, # Pass the URL directly
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

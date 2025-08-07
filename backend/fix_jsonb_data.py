import json
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import logging

# Set up basic logging for the script
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Database Setup (replicated from backend/database.py logic) ---
# Get the database URL from environment variables
# Using SQLALCHEMY_DATABASE_URL as it's common for SQLAlchemy,
# but DATABASE_URL would also work given your .env
SQLALCHEMY_DATABASE_URL = os.getenv("SQLALCHEMY_DATABASE_URL")

if not SQLALCHEMY_DATABASE_URL:
    logger.error("SQLALCHEMY_DATABASE_URL environment variable is not set. Cannot connect to database.")
    exit(1) # Exit if no database URL

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Import your SQLAlchemy models from your project
# Make sure your 'models.py' file is correctly imported relative to 'backend'
try:
    from backend import models # Adjust this import path if your project structure is different
except ImportError:
    logger.error("Could not import models. Please ensure 'backend/models.py' exists and is importable.")
    exit(1)

# --- Data Fixing Logic ---
def fix_double_encoded_jsonb_data():
    db = SessionLocal()
    try:
        logger.info("Starting database JSONB fix script...")

        # Fetch all posts. For very large databases, consider batching.
        posts_to_fix = db.query(models.Post).all()
        
        fixed_posts_count = 0
        for post in posts_to_fix:
            made_changes_on_post = False
            
            # Helper function to attempt decoding
            def decode_json_if_needed(value):
                if isinstance(value, str):
                    try:
                        # Attempt to decode once
                        decoded_value = json.loads(value)
                        # If the result is still a string, it means it was double-encoded
                        if isinstance(decoded_value, str):
                            decoded_value = json.loads(decoded_value)
                        return decoded_value, True # Return decoded value and True for 'changed'
                    except json.JSONDecodeError as e:
                        logger.warning(f"JSONDecodeError for post {post.id}, field type: {type(value)}, value: {value[:100]}... Error: {e}")
                        return value, False # Return original value, no change
                    except Exception as e:
                        logger.error(f"Unexpected error decoding for post {post.id}, value: {value[:100]}... Error: {e}")
                        return value, False
                return value, False # Not a string, no change needed (already decoded by JSONB type)

            # Fix 'hashtags'
            new_hashtags, changed_hashtags = decode_json_if_needed(post.hashtags)
            if changed_hashtags:
                post.hashtags = new_hashtags
                made_changes_on_post = True

            # Fix 'links'
            new_links, changed_links = decode_json_if_needed(post.links)
            if changed_links:
                post.links = new_links
                made_changes_on_post = True

            # Fix 'mentions'
            new_mentions, changed_mentions = decode_json_if_needed(post.mentions)
            if changed_mentions:
                post.mentions = new_mentions
                made_changes_on_post = True

            # Fix 'embeds'
            new_embeds, changed_embeds = decode_json_if_needed(post.embeds)
            if changed_embeds:
                post.embeds = new_embeds
                made_changes_on_post = True
            
            # If any changes were made to the current post, mark it for update
            if made_changes_on_post:
                db.add(post) # Re-add to session to mark as dirty
                fixed_posts_count += 1
                logger.info(f"Fixed JSONB fields for post {post.id} (URI: {post.uri}).")

        # Commit all changes to the database
        db.commit()
        logger.info(f"Database JSONB fix script completed. Total posts with fixes: {fixed_posts_count}")

    except Exception as e:
        db.rollback() # Rollback all changes if an error occurs
        logger.error(f"An unexpected error occurred during the fix script: {e}", exc_info=True)
    finally:
        db.close() # Always close the session

if __name__ == "__main__":
    fix_double_encoded_jsonb_data()

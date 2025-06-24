# backend/auth_utils.py
#
# This file provides helper functions for handling user authentication,
# including password hashing (if applicable for local users) and
# JSON Web Token (JWT) creation and verification.
#
# For Feedmaster, the primary authentication would likely be tied to Bluesky DIDs,
# but a local authentication mechanism (e.g., app passwords for internal users or administrators)
# might be necessary for managing the Feedmaster itself.
#
# This implementation focuses on JWTs for session management and basic password hashing.

import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from passlib.context import CryptContext
from jose import JWTError, jwt
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- Configuration ---
# Get the secret key from environment variables.
# This key is crucial for signing and verifying JWTs.
SECRET_KEY = os.getenv("SECRET_KEY", "your-super-secret-key") # Use a strong default for dev, but load from .env
ALGORITHM = "HS256" # Algorithm for JWT signing
ACCESS_TOKEN_EXPIRE_MINUTES = 30 # How long the access token is valid

# Password hashing context (using bcrypt)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- Password Hashing Functions ---
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a hashed password.
    Useful if you implement local user accounts with passwords.
    """
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """
    Hash a plain password.
    Useful if you implement local user accounts with passwords.
    """
    return pwd_context.hash(password)

# --- JWT Functions ---
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.
    The 'data' dictionary will be encoded into the token's payload.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire}) # Add expiration time to payload
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[dict]:
    """
    Decode and verify a JWT access token.
    Returns the payload if valid, None if invalid or expired.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        # If the token is invalid (e.g., tampered, expired), JWTError is raised
        return None

# Example usage (for testing/demonstration, not for production use directly)
if __name__ == "__main__":
    # Test password hashing
    password = "supersecretpassword"
    hashed_password = get_password_hash(password)
    print(f"Hashed password: {hashed_password}")
    print(f"Verify 'supersecretpassword': {verify_password('supersecretpassword', hashed_password)}")
    print(f"Verify 'wrongpassword': {verify_password('wrongpassword', hashed_password)}")

    # Test JWT creation and decoding
    user_data = {"sub": "did:plc:abcdef1234567890", "handle": "testuser.bsky.social"}
    token = create_access_token(data=user_data)
    print(f"\nGenerated token: {token}")

    decoded_payload = decode_access_token(token)
    print(f"Decoded payload: {decoded_payload}")

    # Simulate expired token (for testing, not typical usage)
    expired_token = create_access_token(data=user_data, expires_delta=timedelta(seconds=-10))
    print(f"Expired token: {expired_token}")
    decoded_expired_payload = decode_access_token(expired_token)
    print(f"Decoded expired payload: {decoded_expired_payload} (should be None)")

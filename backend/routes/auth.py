"""
backend/routes/auth.py — Authentication Router
================================================
Handles registration, login, JWT token refresh, profile loading, and profile updates.
Provides the standard secure JWT authentication dependency `get_current_user`.

Coordination:
- Used by: backend/main.py (registered as router), backend/routes/*.py (for token verification).
"""

from fastapi import APIRouter, Depends, HTTPException, Header, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from backend.database import get_db
import backend.models as models
from backend.auth import (
    hash_password, 
    verify_password, 
    create_tokens,
    verify_token,
    UserResponse,
    TokenResponse,
    TokenRequest
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


# ──────────────────────────────────────────────────────────────────────────
# 1. Pydantic Models for API Payloads
# ──────────────────────────────────────────────────────────────────────────

class UserLogin(BaseModel):
    email: str
    password: str

class UserSignup(BaseModel):
    email: str
    password: str
    full_name: str = None
    phone: str = None
    telegram_handle: str = None
    profile_picture: str = None

class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    telegram_handle: Optional[str] = None
    profile_picture: Optional[str] = None


# ──────────────────────────────────────────────────────────────────────────
# 2. JWT Dependency Injection Validator
# ──────────────────────────────────────────────────────────────────────────

def get_current_user(request_authorization: Optional[str] = Header(None, alias="Authorization"), db: Session = Depends(get_db)) -> models.User:
    """
    Checks incoming headers for a valid JWT Bearer token and returns the current user object.
    Raises 401 Unauthorized if the token is missing, expired, or invalid.
    """
    token = None
    if request_authorization and request_authorization.startswith("Bearer "):
        token = request_authorization[7:]
    
    if not token:
        raise HTTPException(status_code=401, detail="No valid token provided. Have you logged in?")
    
    try:
        payload = verify_token(token)
        user_id: int = payload.get("user_id")
        email: str = payload.get("email")
        
        if user_id is None or email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User not found or inactive")
        
        return user
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


# ──────────────────────────────────────────────────────────────────────────
# 3. Authentication Route Enpoints
# ──────────────────────────────────────────────────────────────────────────

@router.post("/signup", response_model=TokenResponse)
async def signup(user: UserSignup, db: Session = Depends(get_db)):
    """Creates a new user record and issues JWT access/refresh tokens."""
    print(f"[Auth Router] Signup attempt for email: {user.email}")
    existing_user = db.query(models.User).filter(models.User.email == user.email).first()
    if existing_user: 
        print(f"[Auth Router] Signup failed: Email {user.email} already exists.")
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Securely hash user password before database commit
    hashed = hash_password(user.password)
    db_user = models.User(
        email=user.email,
        hashed_password=hashed,
        full_name=user.full_name,
        phone=user.phone,
        telegram_handle=user.telegram_handle,
        profile_picture=user.profile_picture,
        is_active=True
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return create_tokens(db_user.id, db_user.email)


@router.post("/login", response_model=TokenResponse)
async def login(user: UserLogin, response: Response, db: Session = Depends(get_db)):
    """Verifies credentials, issues tokens, and sets HTTP-only cookies."""
    print(f"[Auth Router] Login attempt for email: {user.email}")
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if not db_user or not db_user.is_active or not verify_password(user.password, db_user.hashed_password):
        print(f"[Auth Router] Login failed for email: {user.email}")
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    tokens = create_tokens(db_user.id, db_user.email)
    # Set tokens in secure cookies for frontend convenience
    response.set_cookie(key="access_token", value=tokens.access_token, httponly=True, samesite="lax", max_age=86400)
    response.set_cookie(key="refresh_token", value=tokens.refresh_token, httponly=True, samesite="lax", max_age=604800)
    return tokens


@router.get("/profile", response_model=UserResponse)
async def get_profile(user: models.User = Depends(get_current_user)):
    """Retrieves the authenticated user's profile details."""
    return user


@router.put("/profile", response_model=UserResponse)
async def update_profile(profile_update: UserProfileUpdate, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Updates selected user profile settings."""
    if profile_update.full_name is not None: 
        user.full_name = profile_update.full_name
    if profile_update.phone is not None: 
        user.phone = profile_update.phone
    if profile_update.telegram_handle is not None: 
        user.telegram_handle = profile_update.telegram_handle
    if profile_update.profile_picture is not None: 
        user.profile_picture = profile_update.profile_picture
    
    db.commit()
    db.refresh(user)
    return user


@router.post("/logout")
async def logout(response: Response):
    """Deletes authentication cookie sessions."""
    response.delete_cookie(key="access_token")
    response.delete_cookie(key="refresh_token")
    return {"status": "success", "message": "Logged out successfully"}


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(req: TokenRequest, db: Session = Depends(get_db)):
    """Issues fresh token pairs using a valid refresh token."""
    try:
        payload = verify_token(req.refresh_token)
        user = db.query(models.User).filter(models.User.id == payload.get("user_id")).first()
        if not user or not user.is_active: 
            raise HTTPException(status_code=401, detail="User not found")
        return create_tokens(user.id, user.email)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid refresh token: {str(e)}")


@router.get("/verify")
async def verify_auth(user: Optional[models.User] = Depends(get_current_user)):
    """Convenience endpoint to check active login session."""
    if user:
        return {"status": "valid", "user_id": user.id, "email": user.email, "full_name": user.full_name}
    return {"status": "invalid", "detail": "Token validation failed"}

import re
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app import models
from app.schemas import UserRegister, UserLogin, UserResponse, Token
from app.core import security
from app.database import get_db

router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(user_in: UserRegister, db: Session = Depends(get_db)):
    """Registers a new user account with secure password hashing and returns JWT token."""
    username = user_in.username.strip()
    email = user_in.email.strip().lower()

    # Input validation
    if len(username) < 3 or len(username) > 30:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username must be between 3 and 30 characters long."
        )

    if not re.match(r"^[a-zA-Z0-9_]+$", username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username can only contain alphanumeric characters and underscores."
        )

    if not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide a valid email address."
        )

    # Password strength check
    password_error = security.validate_password_strength(user_in.password)
    if password_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=password_error
        )

    # Check for existing user
    existing_user = db.query(models.User).filter(
        or_(models.User.username == username, models.User.email == email)
    ).first()

    if existing_user:
        if existing_user.username == username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username is already taken."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email address is already registered."
            )

    # Hash password securely
    hashed_pwd = security.get_password_hash(user_in.password)

    # Create new user
    new_user = models.User(
        username=username,
        email=email,
        hashed_password=hashed_pwd
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Issue JWT token
    access_token = security.create_access_token(data={"sub": new_user.username})

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(new_user)
    )


@router.post("/login", response_model=Token)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    """Authenticates user credentials against bcrypt hashes and issues a JWT token."""
    login_id = credentials.username_or_email.strip()
    
    # Uniform error response to prevent user enumeration attacks
    invalid_credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid username/email or password",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user = db.query(models.User).filter(
        or_(models.User.username == login_id, models.User.email == login_id.lower())
    ).first()

    if not user:
        raise invalid_credentials_exc

    if not security.verify_password(credentials.password, user.hashed_password):
        raise invalid_credentials_exc

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your account has been deactivated. Please contact support."
        )

    access_token = security.create_access_token(data={"sub": user.username})

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: models.User = Depends(security.get_current_user)):
    """Returns profile information for the currently authenticated user."""
    return UserResponse.model_validate(current_user)

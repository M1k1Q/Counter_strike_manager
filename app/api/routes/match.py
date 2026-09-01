import re
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app import models
from app.schemas import UserRegister, UserLogin, UserResponse, Token
from app.core import security
from app.database import get_db



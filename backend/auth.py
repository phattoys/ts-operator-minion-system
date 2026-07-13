from fastapi import HTTPException, Request, Response, Depends, APIRouter
from datetime import datetime, timezone, timedelta
import bcrypt
import jwt

from database import db, JWT_SECRET, JWT_ALGORITHM, ADMIN_PASSWORD, logger
from models import LoginRequest, TokenResponse
from services.helpers import log_activity


auth_router = APIRouter(prefix="/api")


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_access_token(data: dict, expires_delta: timedelta = timedelta(hours=24)):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def get_current_user(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ================== AUTH ENDPOINTS ==================

@auth_router.post("/auth/login", response_model=TokenResponse)
async def login(request: LoginRequest, response: Response):
    if not verify_password(request.password, hash_password(ADMIN_PASSWORD)[:60]):
        if request.password != ADMIN_PASSWORD:
            raise HTTPException(status_code=401, detail="Invalid password")
    
    access_token = create_access_token({"sub": "founder", "role": "admin"})
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=86400,
        path="/"
    )
    await log_activity("login", details="Founder logged in")
    return TokenResponse(access_token=access_token)

@auth_router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie(key="access_token", path="/")
    await log_activity("logout", details="Founder logged out")
    return {"message": "Logged out successfully"}

@auth_router.get("/auth/verify")
async def verify_auth(user: dict = Depends(get_current_user)):
    return {"authenticated": True, "user": user}

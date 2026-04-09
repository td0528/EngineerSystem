"""
Authentication API router
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from typing import Optional

from app.database.database import get_db
from app.models.users import User, Supplier

router = APIRouter()

# JWT Configuration
SECRET_KEY = "voniko-factory-management-secret-key-2024"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 hours

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# Fallback for bcrypt version issues on Windows
import hashlib

def _sha256_hash(password: str) -> str:
    """Simple SHA256 hash fallback"""
    return hashlib.sha256(password.encode()).hexdigest()

# Pre-computed hashes for admin123 using different methods
KNOWN_PASSWORDS = {
    "admin123": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.Zy1.hM2rPH.bom",
}


# Pydantic schemas
class Token(BaseModel):
    access_token: str
    token_type: str
    user: dict


class UserCreate(BaseModel):
    username: str
    password: str
    full_name: Optional[str] = None
    full_name_vn: Optional[str] = None
    email: Optional[str] = None
    department: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    username: str
    full_name: Optional[str]
    email: Optional[str]
    department: Optional[str]
    is_active: bool
    
    class Config:
        from_attributes = True


def verify_password(plain_password, hashed_password):
    """Verify password with bcrypt fallback for known passwords"""
    # Check for SHA256 fallback hash first
    if hashed_password and hashed_password.startswith("$sha256$"):
        expected_hash = "$sha256$" + _sha256_hash(plain_password)
        return hashed_password == expected_hash
    
    # Then try bcrypt
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        # Fallback: check if this is a known password with known hash
        if plain_password in KNOWN_PASSWORDS:
            return hashed_password == KNOWN_PASSWORDS[plain_password]
        return False


def get_password_hash(password):
    """Hash password - use bcrypt or fallback to known hash"""
    try:
        return pwd_context.hash(password[:72])
    except Exception:
        # Fallback for known passwords
        if password in KNOWN_PASSWORDS:
            return KNOWN_PASSWORDS[password]
        # Use a simple hash as last resort (not recommended for production)
        return "$sha256$" + _sha256_hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        user_type: str = payload.get("type", "user")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    if user_type == "supplier":
        user = db.query(Supplier).filter(Supplier.code == username).first()
    else:
        user = db.query(User).filter(User.username == username).first()
    
    if user is None:
        raise credentials_exception
    return user


@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """用户登录"""
    user = db.query(User).filter(User.username == form_data.username).first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(status_code=400, detail="用户已被禁用")
    
    access_token = create_access_token(data={"sub": user.username, "type": "user"})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "email": user.email,
            "department": user.department,
            "is_superuser": user.is_superuser
        }
    }


@router.post("/register", response_model=UserResponse)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """用户注册"""
    # Check if username exists
    if db.query(User).filter(User.username == user_data.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    
    # Create new user
    new_user = User(
        username=user_data.username,
        hashed_password=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        full_name_vn=user_data.full_name_vn,
        email=user_data.email,
        department=user_data.department
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return new_user


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return current_user


@router.post("/supplier/login", response_model=Token)
async def supplier_login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """供应商登录 - 使用供应商代码和密码"""
    supplier = db.query(Supplier).filter(Supplier.code == form_data.username).first()
    
    if not supplier or not verify_password(form_data.password, supplier.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="供应商代码或密码错误",
        )
    
    if not supplier.is_active:
        raise HTTPException(status_code=400, detail="供应商账户已被禁用")
    
    access_token = create_access_token(data={"sub": supplier.code, "type": "supplier"})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": supplier.id,
            "code": supplier.code,
            "name": supplier.name,
            "is_supplier": True
        }
    }


@router.get("/users")
async def get_users(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取用户列表"""
    users = db.query(User).offset(skip).limit(limit).all()
    return users

# Standard library imports
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Third-party imports
from dotenv import load_dotenv
import jwt
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from passlib.context import CryptContext
from supabase import create_client, Client

# Optional: type hints
from typing import Literal, Optional, Dict


# ----- LOAD ENVIRONMENT VARIABLES -----
env_path = Path("./env.env")
if not env_path.is_file():
    raise FileNotFoundError(f"Environment file not found: {env_path}")
load_dotenv(env_path)


# ----- CONFIG -----
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("Missing environment variable: SECRET_KEY")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
ACCESS_TOKEN_EXPIRE = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)  # for direct use


# ----- INIT APP -----
app = FastAPI(title="To-Do List API with Multi-User JWT Auth")


# ----- PASSWORD HASHING -----
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")  # bcrypt recommended


# ----- DATABASE CLIENT -----
def get_client() -> Client:
    """Initialize and return a Supabase client."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment")
    return create_client(url, key)


# Singleton-style client
supabase = get_client()


# ----- CONSTANTS -----
TASK_STATUS = Literal["done", "pending"]  # reuse for all task models


# ----- USER MODELS -----
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ----- TASK MODELS -----
class TaskBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    priority: int = Field(..., ge=1)
    status: TASK_STATUS


class TaskCreate(TaskBase):
    pass  # inherits all fields from TaskBase


class TaskRead(TaskBase):
    id: int
    created_on: datetime
    last_modified: datetime


class TaskUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., max_length=500)
    priority: int = Field(..., ge=1)
    status: TASK_STATUS


# ----- SECURITY -----
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# ----- PASSWORD UTILS -----
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against the hashed password."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a plaintext password."""
    return pwd_context.hash(password)


# ----- JWT UTILS -----
def create_access_token(data: Dict[str, str], expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT token with an optional expiry."""
    to_encode = data.copy()
    expire = datetime.utcnow().replace(tzinfo=timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Retrieve the current user based on JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token: missing subject")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Fetch user from Supabase
    response = supabase.table("users").select("*").eq("username", username).execute()
    user = response.data[0] if response.data else None
    
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user


# ----- USER ROUTES -----
@app.post("/register", status_code=status.HTTP_201_CREATED)
def register(user: UserCreate) -> dict:
    """Register a new user with hashed password."""
    hashed_pw = get_password_hash(user.password)

    # Check if username already exists
    existing_user = supabase.table("users").select("username").eq("username", user.username).execute()
    if existing_user.data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists")

    try:
        response = supabase.table("users").insert({
            "username": user.username,
            "password_hash": hashed_pw
        }).execute()

        # If insertion failed for any reason
        if not response.data:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail="Failed to create user")

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Registration failed: {str(e)}")

    return {"msg": "User created successfully", "username": user.username}


@app.post("/token", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends()) -> Token:
    """
    Authenticate user and return JWT access token.
    """
    try:
        # Query Supabase for the user
        response = supabase.table("users").select("*").eq("username", form_data.username).execute()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Login failed: {str(e)}")

    user = response.data[0] if response.data else None

    if not user or not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Create JWT token
    access_token = create_access_token({"sub": user["username"]})

    return Token(access_token=access_token, token_type="bearer")


# ----- TASK ROUTES -----
@app.post("/tasks", response_model=TaskRead, status_code=201)
def create_task(task: TaskCreate, current_user: dict = Depends(get_current_user)):
    now = datetime.now(timezone.utc).isoformat()

    response = supabase.table("tasks").insert({
        "name": task.name.strip(),
        "description": task.description,
        "priority": task.priority,
        "status": task.status,
        "created_on": now,
        "last_modified": now,
        "user_id": current_user["id"]
    }).execute()

    if not response.data:
        raise HTTPException(status_code=500, detail="Task creation failed")

    # Supabase returns the inserted row(s) in response.data
    return response.data[0]


@app.get("/tasks", response_model=list[TaskRead])
def get_tasks(
    sort_by: str = "priority",
    order: str = "desc",
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    # Validate inputs
    allowed_sort_cols = {"priority", "created_on", "last_modified"}
    if sort_by not in allowed_sort_cols:
        sort_by = "priority"

    order = order.lower()
    desc = True if order == "desc" else False

    # Build query
    query = supabase.table("tasks").select("*").eq("user_id", current_user["id"])

    if status in ("done", "pending"):
        query = query.eq("status", status)

    query = query.order(sort_by, desc=desc)

    response = query.execute()

    if not response.data:
        return []

    return response.data



@app.get("/tasks/{task_id}", response_model=TaskRead)
def get_task(task_id: int, current_user: dict = Depends(get_current_user)):
    response = (
        supabase.table("tasks")
        .select("*")
        .eq("id", task_id)
        .eq("user_id", current_user["id"])
        .execute()
    )

    task = response.data[0] if response.data else None

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return task


@app.patch("/tasks/{task_id}", response_model=TaskRead)
def update_task(task_id: int, body: TaskUpdate, current_user: dict = Depends(get_current_user)):
    # Check if the task exists for this user
    exists = (
        supabase.table("tasks")
        .select("id")
        .eq("id", task_id)
        .eq("user_id", current_user["id"])
        .execute()
    )

    if not exists.data:
        raise HTTPException(status_code=404, detail="Task not found")

    now = datetime.now(timezone.utc).isoformat()

    # Perform the update
    response = (
        supabase.table("tasks")
        .update({
            "name": body.name,
            "description": body.description,
            "priority": body.priority,
            "status": body.status,
            "last_modified": now,
        })
        .eq("id", task_id)
        .eq("user_id", current_user["id"])
        .execute()
    )

    if not response.data:
        raise HTTPException(status_code=500, detail="Update failed")

    return response.data[0]


from postgrest.exceptions import APIError

@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, current_user: dict = Depends(get_current_user)):
    try:
        # Check existence
        exists = (
            supabase.table("tasks")
            .select("id")
            .eq("id", task_id)
            .eq("user_id", current_user["id"])
            .execute()
        )

        if not exists.data:
            raise HTTPException(status_code=404, detail="Task not found")

        # Delete
        supabase.table("tasks") \
            .delete() \
            .eq("id", task_id) \
            .eq("user_id", current_user["id"]) \
            .execute()

    except APIError as e:
        raise HTTPException(status_code=500, detail=f"Supabase error: {e}")

    return None


# For Render to make sure backend is okay
@app.get("/health")
def health():
    return {"status": "ok"}

from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from typing import Literal
from passlib.context import CryptContext
import sqlite3
from datetime import datetime, timezone, timedelta
import jwt
import os
from dotenv import load_dotenv

# ----- CONFIG -----
load_dotenv("./env.env")
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("No SECRET_KEY found! Set it in env.env")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15

# ----- INIT APP -----
app = FastAPI(title="To-Do List API with Multi-User JWT Auth")

# ----- PASSWORD HASHING -----
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ----- DATABASE -----
def get_connection():
    conn = sqlite3.connect("tasks.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)
    # Tasks table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            priority INTEGER NOT NULL,
            status TEXT CHECK(status IN ('done','pending')) NOT NULL,
            created_on TEXT NOT NULL,
            last_modified TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ----- MODELS -----
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)

class Token(BaseModel):
    access_token: str
    token_type: str

class TaskCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    priority: int = Field(..., ge=1)
    status: Literal["done", "pending"]

class TaskRead(TaskCreate):
    id: int
    created_on: datetime
    last_modified: datetime

class TaskUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    priority: int = Field(..., ge=1)
    status: Literal["done", "pending"]

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# ----- AUTH UTILS -----
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    conn.close()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

# ----- USER ROUTES -----
@app.post("/register", status_code=201)
def register(user: UserCreate):
    conn = get_connection()
    cursor = conn.cursor()
    hashed_pw = get_password_hash(user.password)
    try:
        cursor.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (user.username, hashed_pw)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="Username already exists")
    conn.close()
    return {"msg": "User created successfully"}

@app.post("/token", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (form_data.username,))
    user = cursor.fetchone()
    conn.close()
    if not user or not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    access_token = create_access_token({"sub": user["username"]})
    return {"access_token": access_token, "token_type": "bearer"}

# ----- TASK ROUTES -----
@app.post("/tasks", response_model=TaskRead, status_code=201)
def create_task(task: TaskCreate, current_user: dict = Depends(get_current_user)):
    now = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO tasks (name, description, priority, status, created_on, last_modified, user_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (task.name.strip(), task.description, task.priority, task.status, now, now, current_user["id"]),
    )
    conn.commit()
    task_id = cursor.lastrowid
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row)

from typing import Optional

@app.get("/tasks", response_model=list[TaskRead])
def get_tasks(
    sort_by: str = "priority",
    order: str = "desc",
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    # Validate inputs to prevent SQL injection
    allowed_sort_cols = {"priority", "created_on", "last_modified"}
    if sort_by not in allowed_sort_cols:
        sort_by = "priority"

    order = order.lower()
    if order not in ("asc", "desc"):
        order = "desc"

    conn = get_connection()
    cursor = conn.cursor()

    # Base query
    sql = "SELECT * FROM tasks WHERE user_id = ?"
    params = [current_user["id"]]

    # Optional filter
    if status in ("done", "pending"):
        sql += " AND status = ?"
        params.append(status)

    # Sorting
    sql += f" ORDER BY {sort_by} {order.upper()}"

    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.get("/tasks/{task_id}", response_model=TaskRead)
def get_task(task_id: int, current_user: dict = Depends(get_current_user)):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE id = ? AND user_id = ?", (task_id, current_user["id"]))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Task not found")
    return dict(row)

@app.patch("/tasks/{task_id}", response_model=TaskRead)
def update_task(task_id: int, body: TaskUpdate, current_user: dict = Depends(get_current_user)):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM tasks WHERE id = ? AND user_id = ?", (task_id, current_user["id"]))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Task not found")
    now = datetime.now(timezone.utc).isoformat()
    cursor.execute(
        """
        UPDATE tasks
        SET name = ?, description = ?, priority = ?, status = ?, last_modified = ?
        WHERE id = ? AND user_id = ?
        """,
        (body.name, body.description, body.priority, body.status, now, task_id, current_user["id"]),
    )
    conn.commit()
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row)

@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, current_user: dict = Depends(get_current_user)):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM tasks WHERE id = ? AND user_id = ?", (task_id, current_user["id"]))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Task not found")
    cursor.execute("DELETE FROM tasks WHERE id = ? AND user_id = ?", (task_id, current_user["id"]))
    conn.commit()
    conn.close()
    return None

# For Render to make sure backend is okay

@app.get("/health")
def health():
    return {"status": "ok"}

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .auth import create_access_token, hash_password, verify_password
from .categories import router as categories_router
from .database import get_conn, init_db
from .expenses import router as expenses_router
from .schemas import LoginRequest, TokenResponse, UserCreate
from .ai import router as ai_router

app = FastAPI(title="Expense Tracker API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    init_db()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/auth/register", response_model=TokenResponse, tags=["auth"])
def register(user: UserCreate):
    with get_conn() as conn:
        if conn.execute("SELECT 1 FROM users WHERE email=%s", (user.email.lower(),)).fetchone():
            raise HTTPException(409, "Email already registered")
        row = conn.execute(
            "INSERT INTO users(email,password_hash) VALUES(%s,%s) RETURNING id",
            (user.email.lower(), hash_password(user.password)),
        ).fetchone()
        user_id = row[0]
        for name in ["Food", "Transport", "Shopping", "Bills"]:
            conn.execute("INSERT INTO categories(user_id,name) VALUES(%s,%s)", (user_id, name))
    return {"access_token": create_access_token(user_id), "token_type": "bearer"}

@app.post("/auth/login", response_model=TokenResponse, tags=["auth"])
def login(data: LoginRequest):
    with get_conn() as conn:
        row = conn.execute("SELECT id,password_hash FROM users WHERE email=%s", (data.email.lower(),)).fetchone()
    if not row or not verify_password(data.password, row[1]):
        raise HTTPException(401, "Invalid email or password")
    return {"access_token": create_access_token(row[0]), "token_type": "bearer"}

app.include_router(expenses_router)
app.include_router(categories_router)
app.include_router(ai_router)

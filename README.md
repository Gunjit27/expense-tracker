# 💰 Expense Tracker

A resume-ready personal expense tracking application built with **FastAPI, PostgreSQL, Streamlit, JWT authentication, explicit SQL, and Ollama**.

## Features

- User registration and login with JWT access tokens
- Secure password hashing with Argon2 via `pwdlib`
- User-isolated expense and category data
- Expense CRUD (create, view, update/delete through API)
- Default categories: Food, Transport, Shopping, Bills
- User-created categories
- Payment methods: UPI, cards, cash, bank transfer, other
- Streamlit dashboard with total spend, monthly spend, transactions, top category, category chart, and monthly trend
- Expense listing/filter-ready REST API
- Ollama-powered natural-language expense assistant
- AI responses are grounded in fixed PostgreSQL queries instead of allowing the LLM to generate arbitrary SQL
- FastAPI Swagger/OpenAPI documentation

## Architecture

```text
Streamlit UI
     |
     | HTTP + JWT
     v
 FastAPI API
  |    |    |
  |    |    +---- Ollama (local LLM)
  |    |
  |    +--------- Auth / Expense / Category logic
  |
  +-------------- PostgreSQL (explicit SQL via psycopg)
```

## Project structure

```text
expense-tracker/
├── app/
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── auth.py
│   ├── expenses.py
│   ├── categories.py
│   └── ai.py
├── ui/
│   └── streamlit_app.py
├── sql/
│   └── schema.sql
├── .env.example
├── requirements.txt
└── README.md
```

## Local setup

### 1. Create PostgreSQL database

Create a database named `expense_tracker` in your local PostgreSQL installation.

### 2. Create environment

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and update the PostgreSQL credentials and JWT secret.

### 3. Install Ollama

Install Ollama locally, then pull a small model:

```bash
ollama pull llama3.2:3b
ollama serve
```

You can change `OLLAMA_MODEL` in `.env` to another installed model.

### 4. Run FastAPI

From the project root:

```bash
uvicorn app.main:app --reload
```

Open the API docs at `http://localhost:8000/docs`.

### 5. Run Streamlit

In another terminal:

```bash
streamlit run ui/streamlit_app.py
```

The UI opens at `http://localhost:8501`.

## API overview

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/auth/register` | Register user and return JWT |
| POST | `/auth/login` | Login and return JWT |
| GET | `/categories` | List user's categories |
| POST | `/categories` | Add category |
| DELETE | `/categories/{id}` | Delete unused category |
| GET | `/expenses` | List user's expenses |
| POST | `/expenses` | Add expense |
| PUT | `/expenses/{id}` | Update expense |
| DELETE | `/expenses/{id}` | Delete expense |
| POST | `/ai/ask` | Ask Ollama about spending |
| GET | `/health` | Health check |

## AI design

The AI assistant deliberately does **not** generate unrestricted SQL. The backend identifies supported analytics questions, executes parameterized SQL against the authenticated user's data, and passes only the resulting context to Ollama for a concise natural-language answer.

This keeps calculations and user-data boundaries in application code while still providing a natural-language interface.

## Resume bullet examples

- Built a full-stack personal expense tracker using **FastAPI, PostgreSQL, Streamlit, JWT authentication, and Ollama**.
- Implemented secure user-scoped CRUD operations with parameterized SQL and Argon2 password hashing.
- Developed an LLM-powered expense analytics assistant that grounds natural-language responses in PostgreSQL aggregations.
- Created an interactive Streamlit dashboard for category, monthly, and transaction-level spending analytics.

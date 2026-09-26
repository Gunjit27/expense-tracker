# 💰 Expense Tracker

[![Tests](https://github.com/Gunjit27/expense-tracker/actions/workflows/tests.yml/badge.svg)](https://github.com/Gunjit27/expense-tracker/actions/workflows/tests.yml)

A full-stack personal expense tracking system that helps users manage expenses, analyze spending, and get AI-powered insights.

---

## 🚀 Overview

This project provides an end-to-end expense management workflow:

* Track daily expenses
* Organize expenses by category
* Analyze spending patterns
* Visualize monthly spending
* Ask natural-language questions about expenses using an LLM

---

## ✨ Features

* 🔐 **User Authentication**

  * JWT-based authentication
  * Secure password hashing

* 💸 **Expense Management**

  * Add, update, delete, and view expenses
  * Filter expenses by category, payment method, and date

* 🏷️ **Categories**

  * Default expense categories
  * Create custom categories

* 📊 **Spending Dashboard**

  * Monthly spending
  * Category breakdown
  * Spending trends
  * Recent transactions

* 🤖 **AI-powered Insights**

  * Ask questions about your spending in plain English (or Hinglish)
  * The LLM picks one of three predefined queries via tool calling; it never writes SQL
  * Answers come only from the query results, and the UI shows which query was used

---

## 🏗️ Architecture

```text
User
  ↓
Streamlit UI
  ↓
FastAPI
  ↓
PostgreSQL
  ↓
Expense Analytics
  ↓
Ollama
  ↓
AI Insights
```

---

## 🤖 How the AI Assistant Works

```text
Question ──► LLM picks a tool + arguments (Ollama tool calling)
                 │
                 ▼
        Pydantic validation ──invalid──► error fed back to the LLM, one retry
                 │
                 ▼
        Dates resolved in code ("last_month" → 2026-08-01..2026-08-31)
                 │
                 ▼
        Fixed, parameterized SQL, always scoped to the logged-in user
                 │
                 ▼
        LLM phrases the answer from the query result only
```

The model can call three tools (`app/ai_tools.py`):

| Tool | Answers questions like |
|---|---|
| `total_spend` | "How much did I spend on Food last month?" |
| `spend_breakdown` | "Where did my money go in August?", "Monthly trend this year" |
| `find_expenses` | "My 3 biggest expenses this year", "Recent UPI payments" |

All three share the same filters: a time period, a category and a payment method.

Why tool calling instead of text-to-SQL: the model can only choose among safe, reviewed queries, and it never sees or sets the user id, so one user can't read another's data through a prompt. Why periods instead of dates: small models are unreliable at date arithmetic, so the model says `last_month` and code works out the dates.

### Evaluation

`evals/router_cases.jsonl` holds 52 questions, including synonyms ("cabs" → Transport), named months, explicit date ranges and Hinglish, each with the expected tool and arguments. The runner scores whether the model produced exactly the right query:

```bash
python -m evals.run_router_eval --baseline --model llama3.1:8b --out evals/results.md
```

| Router | Exact match |
|---|---|
| Old keyword router (baseline) | 10% (5/52) |
| `llama3.1:8b` tool calling | run the command above |

---

## 🛠️ Tech Stack

* **Frontend:** Streamlit
* **Backend:** FastAPI
* **Database:** PostgreSQL
* **Authentication:** JWT 
* **AI:** Ollama (llama3.1:8b) with tool calling
* **Database Driver:** psycopg
* **Dependency Management:** uv

---

## 📂 Project Structure

```text
.
├── app/
│   ├── main.py          # FastAPI application
│   ├── database.py      # Database connection
│   ├── schemas.py       # Pydantic schemas
│   ├── auth.py          # Authentication
│   ├── expenses.py      # Expense APIs
│   ├── categories.py    # Category APIs
│   ├── ai.py            # AI assistant endpoint: plan, run, answer
│   ├── ai_tools.py      # Query tools the LLM can call
│   └── llm.py           # Ollama chat client
│
├── evals/               # Router eval set and runner
│
├── ui/
│   └── streamlit_app.py # Streamlit frontend
│
├── sql/
│   └── schema.sql       # Database schema
│
├── tests/               # pytest API tests (run against PostgreSQL)
│
├── pyproject.toml
├── uv.lock
└── .env.example
```

---

## ⚙️ Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/Gunjit27/expense-tracker.git
cd expense-tracker
```

### 2. Install dependencies

Install [uv](https://docs.astral.sh/uv/) if needed:

```bash
pip install uv
```

Then install the project dependencies:

```bash
uv sync
```

### 3. Configure environment

Create a `.env` file from `.env.example` and configure your PostgreSQL and Ollama settings.

Pull the model the assistant uses (any Ollama model with tool-calling support works; set `OLLAMA_MODEL` to change it):

```bash
ollama pull llama3.1:8b
```

### 4. Run Backend

```bash
uv run uvicorn app.main:app --reload
```

### 5. Run Frontend

```bash
uv run streamlit run ui/streamlit_app.py
```

### 6. Run Tests

The API tests run against a real PostgreSQL database. Create an empty test database (tables are created automatically, and all rows are wiped between tests, so don't point it at real data):

```bash
createdb expense_tracker_test
pip install -r requirements-dev.txt
pytest
```

Set `TEST_DATABASE_URL` if your test database isn't at `postgresql://postgres:postgres@localhost:5432/expense_tracker_test`. Ollama is stubbed out, so it doesn't need to be running.

The same suite runs on every push and pull request via GitHub Actions.

---

## 🧪 How It Works

1. Register or log in
2. Add and categorize expenses
3. View spending through the dashboard
4. Filter and analyze transactions
5. Ask questions about your spending using the AI assistant

---

## 💡 Use Cases

* Personal expense tracking
* Monthly budget analysis
* Spending pattern analysis
* Financial insights
* Expense categorization
* Natural-language financial queries

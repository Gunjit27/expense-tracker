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

  * Ask questions about your spending
  * Get insights using Ollama and your expense data

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

## 🛠️ Tech Stack

* **Frontend:** Streamlit
* **Backend:** FastAPI
* **Database:** PostgreSQL
* **Authentication:** JWT 
* **AI:** Ollama
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
│   └── ai.py            # AI functionality
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

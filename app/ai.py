import os
from datetime import date

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .auth import get_current_user
from .database import get_conn

router = APIRouter(prefix="/ai", tags=["ai"])
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")


class Question(BaseModel):
    question: str


def fetch_context(question: str, user_id: int):
    q = question.lower()
    today = date.today()
    with get_conn() as conn:
        if any(k in q for k in ["highest", "largest", "biggest", "most expensive"]):
            rows = conn.execute("""
                SELECT e.amount, c.name, e.payment_method, e.expense_date, COALESCE(e.description,'')
                FROM expenses e JOIN categories c ON c.id=e.category_id
                WHERE e.user_id=%s ORDER BY e.amount DESC LIMIT 5
            """, (user_id,)).fetchall()
            return "Top 5 expenses: " + repr(rows)
        if "category" in q and any(k in q for k in ["most", "highest", "spend"]):
            rows = conn.execute("""
                SELECT c.name, SUM(e.amount) total
                FROM expenses e JOIN categories c ON c.id=e.category_id
                WHERE e.user_id=%s GROUP BY c.name ORDER BY total DESC
            """, (user_id,)).fetchall()
            return "Spending by category: " + repr(rows)
        if "payment" in q or "upi" in q or "bank transfer" in q:
            rows = conn.execute("""
                SELECT payment_method, SUM(amount) total, COUNT(*) transactions
                FROM expenses WHERE user_id=%s GROUP BY payment_method ORDER BY total DESC
            """, (user_id,)).fetchall()
            return "Spending by payment method: " + repr(rows)
        if "this month" in q or "monthly" in q:
            rows = conn.execute("""
                SELECT COALESCE(SUM(amount),0), COUNT(*) FROM expenses
                WHERE user_id=%s AND date_trunc('month', expense_date)=date_trunc('month', %s::date)
            """, (user_id, today)).fetchone()
            return f"Current month total and transactions: {rows}"
        rows = conn.execute("""
            SELECT COALESCE(SUM(amount),0), COUNT(*) FROM expenses WHERE user_id=%s
        """, (user_id,)).fetchone()
        return f"All-time total and transactions: {rows}"


def ask_ollama(question: str, context: str) -> str:
    prompt = f"""You are an expense analytics assistant. Answer using ONLY the database context below.
Do not invent numbers. Keep the answer concise and mention currency as INR (₹) when appropriate.

Question: {question}
Database context: {context}
"""
    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=60,
        )
        response.raise_for_status()
        return response.json().get("response", "No answer returned by Ollama.").strip()
    except requests.RequestException as exc:
        raise HTTPException(503, f"Ollama is unavailable: {exc}")


@router.post("/ask")
def ask(question: Question, user=Depends(get_current_user)):
    context = fetch_context(question.question, user["id"])
    return {"answer": ask_ollama(question.question, context)}

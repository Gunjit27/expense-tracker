from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from .auth import get_current_user
from .database import get_conn
from .schemas import ExpenseCreate

router = APIRouter(prefix="/expenses", tags=["expenses"])


@router.post("")
def create_expense(expense: ExpenseCreate, user=Depends(get_current_user)):
    with get_conn() as conn:
        category = conn.execute(
            "SELECT id FROM categories WHERE id = %s AND user_id = %s",
            (expense.category_id, user["id"]),
        ).fetchone()
        if not category:
            raise HTTPException(400, "Invalid category")

        row = conn.execute(
            """
            INSERT INTO expenses (user_id, amount, category_id, payment_method, expense_date, description)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, amount, category_id, payment_method, expense_date, description, created_at
            """,
            (user["id"], expense.amount, expense.category_id, expense.payment_method,
             expense.expense_date, expense.description),
        ).fetchone()
    return {"id": row[0], "amount": row[1], "category_id": row[2], "payment_method": row[3],
            "expense_date": row[4], "description": row[5], "created_at": row[6]}


@router.get("")
def list_expenses(
    category_id: Optional[int] = None,
    payment_method: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    user=Depends(get_current_user),
):
    clauses = ["e.user_id = %s"]
    params = [user["id"]]
    if category_id:
        clauses.append("e.category_id = %s"); params.append(category_id)
    if payment_method:
        clauses.append("e.payment_method = %s"); params.append(payment_method)
    if start_date:
        clauses.append("e.expense_date >= %s"); params.append(start_date)
    if end_date:
        clauses.append("e.expense_date <= %s"); params.append(end_date)

    sql = f"""
        SELECT e.id, e.amount, e.category_id, c.name, e.payment_method,
               e.expense_date, e.description, e.created_at
        FROM expenses e JOIN categories c ON c.id = e.category_id
        WHERE {' AND '.join(clauses)}
        ORDER BY e.expense_date DESC, e.created_at DESC
    """
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [
        {"id": r[0], "amount": r[1], "category_id": r[2], "category_name": r[3],
         "payment_method": r[4], "expense_date": r[5], "description": r[6], "created_at": r[7]}
        for r in rows
    ]


@router.put("/{expense_id}")
def update_expense(expense_id: int, expense: ExpenseCreate, user=Depends(get_current_user)):
    with get_conn() as conn:
        valid = conn.execute(
            "SELECT 1 FROM categories WHERE id = %s AND user_id = %s", (expense.category_id, user["id"])
        ).fetchone()
        if not valid:
            raise HTTPException(400, "Invalid category")
        row = conn.execute(
            """
            UPDATE expenses
            SET amount=%s, category_id=%s, payment_method=%s, expense_date=%s, description=%s
            WHERE id=%s AND user_id=%s
            RETURNING id
            """,
            (expense.amount, expense.category_id, expense.payment_method, expense.expense_date,
             expense.description, expense_id, user["id"]),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Expense not found")
    return {"message": "Expense updated"}


@router.delete("/{expense_id}")
def delete_expense(expense_id: int, user=Depends(get_current_user)):
    with get_conn() as conn:
        row = conn.execute(
            "DELETE FROM expenses WHERE id=%s AND user_id=%s RETURNING id", (expense_id, user["id"])
        ).fetchone()
        if not row:
            raise HTTPException(404, "Expense not found")
    return {"message": "Expense deleted"}

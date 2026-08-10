from fastapi import APIRouter, Depends, HTTPException

from .auth import get_current_user
from .database import get_conn
from .schemas import CategoryCreate

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("")
def list_categories(user=Depends(get_current_user)):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, name FROM categories WHERE user_id=%s ORDER BY name", (user["id"],)
        ).fetchall()
    return [{"id": r[0], "name": r[1]} for r in rows]


@router.post("")
def create_category(category: CategoryCreate, user=Depends(get_current_user)):
    with get_conn() as conn:
        try:
            row = conn.execute(
                "INSERT INTO categories(user_id,name) VALUES(%s,%s) RETURNING id,name",
                (user["id"], category.name.strip()),
            ).fetchone()
        except Exception as exc:
            if "duplicate key" in str(exc).lower():
                raise HTTPException(409, "Category already exists")
            raise
    return {"id": row[0], "name": row[1]}


@router.delete("/{category_id}")
def delete_category(category_id: int, user=Depends(get_current_user)):
    with get_conn() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM expenses WHERE category_id=%s AND user_id=%s", (category_id, user["id"])
        ).fetchone()[0]
        if count:
            raise HTTPException(400, "Cannot delete a category that has expenses")
        row = conn.execute(
            "DELETE FROM categories WHERE id=%s AND user_id=%s RETURNING id", (category_id, user["id"])
        ).fetchone()
        if not row:
            raise HTTPException(404, "Category not found")
    return {"message": "Category deleted"}

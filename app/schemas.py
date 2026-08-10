from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class CategoryResponse(BaseModel):
    id: int
    name: str


class ExpenseCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    category_id: int
    payment_method: str = Field(min_length=1, max_length=40)
    expense_date: date
    description: Optional[str] = Field(default=None, max_length=500)


class ExpenseResponse(ExpenseCreate):
    id: int
    category_name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

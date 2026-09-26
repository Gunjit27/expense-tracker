"""Query tools the AI assistant can call.

The LLM never writes SQL. It picks one of these tools and fills in its
arguments, which are validated with Pydantic. Each tool runs a fixed,
parameterized query that is always scoped to the logged-in user; the model
never sees or sets the user id.
"""
import json
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

# Must match the payment methods offered in the Streamlit UI.
PAYMENT_METHODS = ["UPI", "Credit Card", "Debit Card", "Cash", "Bank Transfer", "Other"]

Period = Literal[
    "all_time", "today", "this_week", "last_7_days", "this_month", "last_month",
    "last_30_days", "this_year", "last_year", "month", "custom",
]


class ToolArgError(ValueError):
    """Raised when the model picks an unknown tool or passes invalid arguments."""


class Filters(BaseModel):
    period: Period = Field(
        "all_time",
        description="Time window. Use 'month' with `month` for a named month, "
                    "'custom' with start_date/end_date for explicit dates.",
    )
    month: Optional[str] = Field(
        None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
        description="YYYY-MM, only when period is 'month'.",
    )
    start_date: Optional[date] = Field(None, description="YYYY-MM-DD, only when period is 'custom'.")
    end_date: Optional[date] = Field(None, description="YYYY-MM-DD, only when period is 'custom'.")
    category: Optional[str] = Field(
        None, description="Only when the question is about one category. Must be one of the user's categories.",
    )
    payment_method: Optional[Literal["UPI", "Credit Card", "Debit Card", "Cash", "Bank Transfer", "Other"]] = Field(
        None, description="Only when the question names a payment method.",
    )

    @field_validator("*", mode="before")
    @classmethod
    def blank_to_none(cls, v):
        # Small models often send "" or "null" for arguments they mean to leave out.
        if isinstance(v, str) and v.strip().lower() in ("", "null", "none"):
            return None
        return v

    @model_validator(mode="after")
    def check_period_args(self):
        if self.period == "all_time" and self.month:
            self.period = "month"
        if self.period == "month" and not self.month:
            raise ValueError("period 'month' needs `month` as YYYY-MM")
        if self.period == "custom" and not (self.start_date or self.end_date):
            raise ValueError("period 'custom' needs start_date and/or end_date")
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date is after end_date")
        return self


class TotalSpendArgs(Filters):
    pass


class SpendBreakdownArgs(Filters):
    group_by: Literal["category", "payment_method", "month"] = Field(
        description="What to group the spending by.",
    )


class FindExpensesArgs(Filters):
    order_by: Literal["amount", "date"] = Field(
        "amount", description="'amount' for the biggest expenses, 'date' for the most recent.",
    )
    limit: int = Field(5, ge=1, le=20, description="How many expenses to return.")


TOOLS = {
    "total_spend": (
        TotalSpendArgs,
        "Total amount spent and number of transactions, optionally filtered by time, category or payment method.",
    ),
    "spend_breakdown": (
        SpendBreakdownArgs,
        "Spending grouped by category, payment method or month. Use for 'which category/method/month' "
        "questions, breakdowns and trends.",
    ),
    "find_expenses": (
        FindExpensesArgs,
        "List individual expenses, either the biggest ones or the most recent ones.",
    ),
}


def _tool_schema(model: type[BaseModel]) -> dict:
    """Flatten a Pydantic JSON schema into the simple shape small models handle best."""
    schema = model.model_json_schema()
    props = {}
    for name, field in schema["properties"].items():
        branch = next((b for b in field.get("anyOf", [field]) if b.get("type") != "null"), field)
        prop = {k: v for k, v in branch.items() if k in ("type", "enum", "format", "minimum", "maximum")}
        if "const" in branch:
            prop["enum"] = [branch["const"]]
        if "description" in field:
            prop["description"] = field["description"]
        props[name] = prop
    return {"type": "object", "properties": props, "required": schema.get("required", [])}


TOOL_SPECS = [
    {"type": "function", "function": {"name": name, "description": desc, "parameters": _tool_schema(model)}}
    for name, (model, desc) in TOOLS.items()
]


@dataclass
class ToolCall:
    name: str
    args: Filters


def parse_tool_call(name: str, raw_args, categories: list[str]) -> ToolCall:
    """Validate a tool call from the model. Error messages are written to be fed back to it."""
    if name not in TOOLS:
        raise ToolArgError(f"Unknown tool '{name}'. Available tools: {', '.join(TOOLS)}")
    if isinstance(raw_args, str):
        try:
            raw_args = json.loads(raw_args or "{}")
        except json.JSONDecodeError:
            raise ToolArgError("Arguments must be a JSON object")
    try:
        args = TOOLS[name][0].model_validate(raw_args or {})
    except ValidationError as exc:
        problems = "; ".join(f"{'.'.join(map(str, e['loc'])) or 'arguments'}: {e['msg']}" for e in exc.errors())
        raise ToolArgError(f"Invalid arguments for {name}: {problems}")
    if args.category:
        match = next((c for c in categories if c.lower() == args.category.strip().lower()), None)
        if not match:
            raise ToolArgError(
                f"Unknown category '{args.category}'. Use one of: {', '.join(categories)}, or leave it out."
            )
        args.category = match
    return ToolCall(name, args)


def resolve_dates(f: Filters, today: date) -> tuple[Optional[date], Optional[date]]:
    """Turn a period into an inclusive date range. Done in code, not by the model."""
    if f.period == "today":
        return today, today
    if f.period == "this_week":
        return today - timedelta(days=today.weekday()), today
    if f.period == "last_7_days":
        return today - timedelta(days=6), today
    if f.period == "last_30_days":
        return today - timedelta(days=29), today
    if f.period == "this_month":
        return today.replace(day=1), today
    if f.period == "last_month":
        end = today.replace(day=1) - timedelta(days=1)
        return end.replace(day=1), end
    if f.period == "this_year":
        return date(today.year, 1, 1), today
    if f.period == "last_year":
        return date(today.year - 1, 1, 1), date(today.year - 1, 12, 31)
    if f.period == "month":
        year, month = map(int, f.month.split("-"))
        return date(year, month, 1), date(year, month, monthrange(year, month)[1])
    if f.period == "custom":
        return f.start_date, f.end_date
    return None, None


GROUP_BY_SQL = {
    "category": "c.name",
    "payment_method": "e.payment_method",
    "month": "to_char(date_trunc('month', e.expense_date), 'YYYY-MM')",
}
ORDER_BY_SQL = {
    "amount": "e.amount DESC",
    "date": "e.expense_date DESC, e.created_at DESC",
}


def run_tool(conn, user_id: int, call: ToolCall, today: date) -> dict:
    args = call.args
    start, end = resolve_dates(args, today)
    clauses, params = ["e.user_id = %s"], [user_id]
    if start:
        clauses.append("e.expense_date >= %s"); params.append(start)
    if end:
        clauses.append("e.expense_date <= %s"); params.append(end)
    if args.category:
        clauses.append("c.name = %s"); params.append(args.category)
    if args.payment_method:
        clauses.append("e.payment_method = %s"); params.append(args.payment_method)
    where = " AND ".join(clauses)
    base = f"FROM expenses e JOIN categories c ON c.id = e.category_id WHERE {where}"

    result = {"date_range": {"start": start and start.isoformat(), "end": end and end.isoformat()}}
    if call.name == "total_spend":
        total, count = conn.execute(f"SELECT COALESCE(SUM(e.amount), 0), COUNT(*) {base}", params).fetchone()
        result.update(total=float(total), transactions=count)
    elif call.name == "spend_breakdown":
        # group_by and order_by come from Literal-validated fields, never from raw model text.
        key = GROUP_BY_SQL[args.group_by]
        order = "1" if args.group_by == "month" else "2 DESC"
        rows = conn.execute(
            f"SELECT {key}, SUM(e.amount), COUNT(*) {base} GROUP BY 1 ORDER BY {order}", params
        ).fetchall()
        result["groups"] = [{args.group_by: r[0], "total": float(r[1]), "transactions": r[2]} for r in rows]
    elif call.name == "find_expenses":
        rows = conn.execute(
            f"SELECT e.expense_date, e.amount, c.name, e.payment_method, COALESCE(e.description, '') "
            f"{base} ORDER BY {ORDER_BY_SQL[args.order_by]} LIMIT %s",
            [*params, args.limit],
        ).fetchall()
        result["expenses"] = [
            {"date": r[0].isoformat(), "amount": float(r[1]), "category": r[2],
             "payment_method": r[3], "description": r[4]}
            for r in rows
        ]
    return result

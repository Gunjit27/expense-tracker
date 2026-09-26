"""Natural-language questions about spending, answered with LLM tool calling.

Flow for one question:
1. plan: the LLM picks a tool from ai_tools.TOOLS and fills in its arguments.
   Invalid arguments are fed back to the model for one retry.
2. run: the chosen tool runs a fixed, parameterized SQL query scoped to the user.
3. answer: the LLM phrases the query result as a short answer.
"""
import json
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .ai_tools import PAYMENT_METHODS, TOOL_SPECS, ToolArgError, ToolCall, parse_tool_call, run_tool
from .auth import get_current_user
from .database import get_conn
from .llm import LLMError, OllamaClient

router = APIRouter(prefix="/ai", tags=["ai"])
MAX_ATTEMPTS = 2


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=500)


class PlanningError(RuntimeError):
    pass


def planner_prompt(today: date, categories: list[str]) -> str:
    return f"""You turn questions about a user's personal expenses into exactly one tool call.
Today is {today:%A, %d %B %Y}.
The user's categories are: {", ".join(categories)}.
Payment methods are: {", ".join(PAYMENT_METHODS)}.

Rules:
- Always call exactly one tool. Never answer in text.
- Pick the period that matches the question. Leave it as all_time if no time is mentioned.
- For a named month, use period "month" with month as YYYY-MM, taking the most recent such month that is not in the future.
- Use period "custom" with start_date/end_date only for explicit dates or date ranges.
- Set category only when the question is about one category. Map synonyms to the closest category above
  (for example groceries or restaurants to a food category, cabs or fuel to a transport category).
- Set payment_method only when the question names one.
- Questions may be in Hinglish; interpret them the same way."""


def plan(question: str, today: date, categories: list[str], llm) -> tuple[ToolCall, int]:
    """Ask the model for a tool call. Returns the validated call and the number of attempts used."""
    messages = [
        {"role": "system", "content": planner_prompt(today, categories)},
        {"role": "user", "content": question},
    ]
    error = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        message = llm.chat(messages, tools=TOOL_SPECS)
        calls = message.get("tool_calls") or []
        if not calls:
            error = "You must call one of the tools."
            messages += [message, {"role": "user", "content": error}]
            continue
        function = calls[0]["function"]
        try:
            return parse_tool_call(function["name"], function.get("arguments"), categories), attempt
        except ToolArgError as exc:
            error = str(exc)
            messages += [message, {"role": "tool", "content": f"Error: {error}. Call the tool again with fixed arguments."}]
    raise PlanningError(error)


ANSWER_PROMPT = """You are an expense analytics assistant. Answer the user's question using ONLY the data below.
Do not invent numbers. Amounts are in INR (₹). If the data is empty or the total is 0, say no matching expenses were found.
Keep the answer to one or two sentences."""


def answer(question: str, call: ToolCall, result: dict, llm) -> str:
    data = {"tool": call.name, "filters": call.args.model_dump(mode="json", exclude_none=True), "result": result}
    message = llm.chat([
        {"role": "system", "content": ANSWER_PROMPT},
        {"role": "user", "content": f"Question: {question}\n\nData: {json.dumps(data, ensure_ascii=False)}"},
    ])
    return (message.get("content") or "").strip()


def get_llm() -> OllamaClient:
    return OllamaClient()


@router.post("/ask")
def ask(question: Question, user=Depends(get_current_user), llm=Depends(get_llm)):
    today = date.today()
    with get_conn() as conn:
        categories = [r[0] for r in conn.execute(
            "SELECT name FROM categories WHERE user_id = %s ORDER BY name", (user["id"],)
        ).fetchall()]
    try:
        call, _ = plan(question.question, today, categories, llm)
        with get_conn() as conn:
            result = run_tool(conn, user["id"], call, today)
        text = answer(question.question, call, result, llm)
    except LLMError as exc:
        raise HTTPException(503, str(exc))
    except PlanningError:
        raise HTTPException(
            422, "Couldn't turn that into a query. Try something like 'How much did I spend on Food last month?'"
        )
    return {
        "answer": text,
        "tool": call.name,
        "arguments": call.args.model_dump(mode="json", exclude_none=True),
        "data": result,
    }

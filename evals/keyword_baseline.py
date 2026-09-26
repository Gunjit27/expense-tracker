"""The keyword router the assistant used before tool calling, kept as an eval baseline.

It mirrors the old fetch_context() branches in app/ai.py, expressed as the tool
call each branch was equivalent to.
"""


def keyword_plan(question: str) -> tuple[str, dict]:
    q = question.lower()
    if any(k in q for k in ["highest", "largest", "biggest", "most expensive"]):
        return "find_expenses", {"order_by": "amount", "limit": 5}
    if "category" in q and any(k in q for k in ["most", "highest", "spend"]):
        return "spend_breakdown", {"group_by": "category"}
    if "payment" in q or "upi" in q or "bank transfer" in q:
        return "spend_breakdown", {"group_by": "payment_method"}
    if "this month" in q or "monthly" in q:
        return "total_spend", {"period": "this_month"}
    return "total_spend", {}

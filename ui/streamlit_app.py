import os
from datetime import date, timedelta

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Expense Tracker", page_icon="💰", layout="wide")


def api(method, path, **kwargs):
    headers = kwargs.pop("headers", {})
    if st.session_state.get("token"):
        headers["Authorization"] = f"Bearer {st.session_state.token}"
    try:
        r = requests.request(method, f"{API_URL}{path}", headers=headers, timeout=15, **kwargs)
        if r.status_code >= 400:
            try:
                detail = r.json().get("detail", r.text)
            except Exception:
                detail = r.text
            st.error(detail)
            return None
        return r.json()
    except requests.RequestException as exc:
        st.error(f"API unavailable: {exc}")
        return None


def auth_page():
    st.title("💰 Expense Tracker")
    tab1, tab2 = st.tabs(["Login", "Register"])
    with tab1:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Login", type="primary"):
            data = api("POST", "/auth/login", json={"email": email, "password": password})
            if data:
                st.session_state.token = data["access_token"]
                st.rerun()
    with tab2:
        email = st.text_input("Email", key="register_email")
        password = st.text_input("Password (8+ characters)", type="password", key="register_password")
        if st.button("Create account", type="primary"):
            data = api("POST", "/auth/register", json={"email": email, "password": password})
            if data:
                st.session_state.token = data["access_token"]
                st.rerun()


def dashboard():
    st.title("Dashboard")
    expenses = api("GET", "/expenses") or []
    df = pd.DataFrame(expenses)
    if df.empty:
        st.info("No expenses yet. Add your first expense from the sidebar.")
        return
    df["amount"] = pd.to_numeric(df["amount"])
    df["expense_date"] = pd.to_datetime(df["expense_date"])
    total = df["amount"].sum()
    month_total = df[df["expense_date"].dt.to_period("M") == pd.Timestamp.today().to_period("M")]["amount"].sum()
    top_category = df.groupby("category_name")["amount"].sum().sort_values(ascending=False).index[0]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total spend", f"₹{total:,.2f}")
    c2.metric("This month", f"₹{month_total:,.2f}")
    c3.metric("Transactions", len(df))
    c4.metric("Top category", top_category)
    left, right = st.columns(2)
    with left:
        st.subheader("Spend by category")
        st.bar_chart(df.groupby("category_name")["amount"].sum())
    with right:
        st.subheader("Monthly trend")
        monthly = df.set_index("expense_date").resample("ME")["amount"].sum()
        st.line_chart(monthly)
    st.subheader("Recent transactions")
    st.dataframe(df[["expense_date", "category_name", "amount", "payment_method", "description"]].head(10), use_container_width=True)


def add_expense():
    st.title("Add Expense")
    categories = api("GET", "/categories") or []
    if not categories:
        st.warning("Create a category first.")
        return
    with st.form("expense_form"):
        amount = st.number_input("Amount (₹)", min_value=0.01, step=100.0)
        category = st.selectbox("Category", categories, format_func=lambda x: x["name"])
        payment = st.selectbox("Payment method", ["UPI", "Credit Card", "Debit Card", "Cash", "Bank Transfer", "Other"])
        expense_date = st.date_input("Date", value=date.today())
        description = st.text_area("Description (optional)")
        submitted = st.form_submit_button("Save expense", type="primary")
    if submitted:
        data = api("POST", "/expenses", json={"amount": amount, "category_id": category["id"],
            "payment_method": payment, "expense_date": str(expense_date), "description": description or None})
        if data:
            st.success("Expense added.")


def manage_expenses():
    st.title("Expenses")
    categories = api("GET", "/categories") or []
    category_map = {c["id"]: c["name"] for c in categories}
    df_data = api("GET", "/expenses") or []
    df = pd.DataFrame(df_data)
    if df.empty:
        st.info("No expenses found.")
        return
    df["amount"] = pd.to_numeric(df["amount"])
    st.dataframe(df[["id", "expense_date", "category_name", "amount", "payment_method", "description"]], use_container_width=True)
    st.divider()
    st.subheader("Delete expense")
    expense_id = st.number_input("Expense ID", min_value=1, step=1)
    if st.button("Delete", type="secondary"):
        if api("DELETE", f"/expenses/{expense_id}"):
            st.success("Deleted.")
            st.rerun()


def categories_page():
    st.title("Categories")
    categories = api("GET", "/categories") or []
    st.write(", ".join(c["name"] for c in categories))
    name = st.text_input("New category")
    if st.button("Add category") and name.strip():
        if api("POST", "/categories", json={"name": name.strip()}):
            st.success("Category added.")
            st.rerun()


def ai_page():
    st.title("🤖 AI Expense Assistant")
    st.caption("Ask questions about your spending. Ollama answers using SQL-backed expense data.")
    question = st.text_input("Ask a question", placeholder="What was my highest spending?")
    if st.button("Ask", type="primary") and question.strip():
        with st.spinner("Thinking..."):
            data = api("POST", "/ai/ask", json={"question": question})
        if data:
            st.success(data["answer"])


def main():
    if not st.session_state.get("token"):
        auth_page()
        return
    with st.sidebar:
        st.title("Expense Tracker")
        page = st.radio("Navigate", ["Dashboard", "Add Expense", "Expenses", "Categories", "AI Assistant"])
        if st.button("Logout"):
            st.session_state.clear()
            st.rerun()
    {"Dashboard": dashboard, "Add Expense": add_expense, "Expenses": manage_expenses,
     "Categories": categories_page, "AI Assistant": ai_page}[page]()


if __name__ == "__main__":
    main()

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Depends
from security import verify_token
import os
import sqlite3
from typing import Any, Dict, List

DB_PATH = os.getenv("DB_PATH", "./data/CRM/crm_wm.db")

app = FastAPI(
    title="Wealth Management RM Insights API",
    description="FastAPI routes for relationship-management insights over the synthetic SQLite CRM database.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_conn() -> sqlite3.Connection:
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=500, detail=f"Database file not found: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def rows_to_dicts(rows) -> List[Dict[str, Any]]:
    return [dict(row) for row in rows]


@app.get("/health")
def health(user=Depends(verify_token)) -> Dict[str, Any]:
    conn = get_conn()
    try:
        tables = [
            "customers", "advisors", "risk_profiles", "accounts",
            "portfolios", "holdings", "transactions", "interactions"
        ]
        counts = {}
        for table in tables:
            counts[table] = conn.execute(f"SELECT COUNT(*) AS cnt FROM {table}").fetchone()["cnt"]
        return {
            "status": "ok",
            "database": DB_PATH,
            "table_counts": counts
        }
    finally:
        conn.close()

@app.get("/customer/{customer_id}/overview")
def customer_overview(customer_id: int, user=Depends(verify_token)):
    conn = get_conn()
    try:
        query = """
        SELECT 
            c.customer_id,
            c.customer_name,
            c.country,
            c.city,
            c.customer_segment,
            rp.risk_tolerance,
            ROUND(COALESCE(SUM(p.current_value), 0), 2) AS total_aum,
            COUNT(DISTINCT a.account_id) AS account_count,
            COUNT(DISTINCT p.portfolio_id) AS portfolio_count,
            MAX(i.interaction_date) AS last_interaction
        FROM customers c
        LEFT JOIN risk_profiles rp ON c.customer_id = rp.customer_id
        LEFT JOIN accounts a ON c.customer_id = a.customer_id
        LEFT JOIN portfolios p ON a.account_id = p.account_id
        LEFT JOIN interactions i ON c.customer_id = i.customer_id
        WHERE c.customer_id = ?
        GROUP BY c.customer_id
        """

        result = conn.execute(query, (customer_id,)).fetchone()

        if not result:
            raise HTTPException(status_code=404, detail="Customer not found")

        return dict(result)
    finally:
        conn.close()

@app.get("/customer/{customer_id}/interactions")
def customer_interactions(customer_id: int, limit: int = 20, user=Depends(verify_token)):
    conn = get_conn()
    try:
        query = """
        SELECT 
            i.interaction_id,
            i.interaction_date,
            i.interaction_type,
            i.sentiment,
            i.notes,
            a.advisor_name
        FROM interactions i
        JOIN advisors a ON i.advisor_id = a.advisor_id
        WHERE i.customer_id = ?
        ORDER BY i.interaction_date DESC
        LIMIT ?
        """

        rows = conn.execute(query, (customer_id, limit)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

@app.get("/customer/{customer_id}/portfolio")
def customer_portfolio(customer_id: int, user= Depends(verify_token)):
    conn = get_conn()
    try:
        query = """
        SELECT 
            p.portfolio_id,
            p.portfolio_type,
            p.current_value,
            h.asset_class,
            h.instrument_name,
            h.market_value
        FROM portfolios p
        JOIN accounts a ON p.account_id = a.account_id
        LEFT JOIN holdings h ON p.portfolio_id = h.portfolio_id
        WHERE a.customer_id = ?
        """

        rows = conn.execute(query, (customer_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

@app.get("/customer/{customer_id}/transactions")
def customer_transactions(customer_id: int, limit: int = 20, user=Depends(verify_token)):
    conn = get_conn()
    try:
        query = """
        SELECT 
            t.transaction_id,
            t.transaction_date,
            t.transaction_type,
            t.amount
        FROM transactions t
        JOIN accounts a ON t.account_id = a.account_id
        WHERE a.customer_id = ?
        ORDER BY t.transaction_date DESC
        LIMIT ?
        """

        rows = conn.execute(query, (customer_id, limit)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

@app.get("/customer/{customer_id}/risk-analysis")
def customer_risk(customer_id: int, user=Depends(verify_token)):
    conn = get_conn()
    try:
        query = """
        SELECT 
            ROUND(COALESCE(SUM(p.current_value), 0), 2) AS total_aum,
            COUNT(i.interaction_id) AS total_interactions,
            SUM(CASE WHEN i.sentiment = 'Negative' THEN 1 ELSE 0 END) AS negative_count,
            MAX(i.interaction_date) AS last_interaction
        FROM customers c
        LEFT JOIN accounts a ON c.customer_id = a.customer_id
        LEFT JOIN portfolios p ON a.account_id = p.account_id
        LEFT JOIN interactions i ON c.customer_id = i.customer_id
        WHERE c.customer_id = ?
        """

        r = conn.execute(query, (customer_id,)).fetchone()

        if not r:
            raise HTTPException(status_code=404, detail="Customer not found")

        risk = "Low"
        if r["negative_count"] >= 2:
            risk = "High"
        elif r["negative_count"] >= 1:
            risk = "Medium"

        return {
            **dict(r),
            "risk_level": risk
        }
    finally:
        conn.close()


@app.get("/customer/{customer_id}/brief")
def customer_brief(customer_id: int, user=Depends(verify_token)):
    conn = get_conn()
    try:
        overview = conn.execute("""
            SELECT customer_name, customer_segment 
            FROM customers WHERE customer_id = ?
        """, (customer_id,)).fetchone()

        if not overview:
            raise HTTPException(status_code=404, detail="Customer not found")

        interactions = conn.execute("""
            SELECT sentiment, notes
            FROM interactions
            WHERE customer_id = ?
            ORDER BY interaction_date DESC
            LIMIT 5
        """, (customer_id,)).fetchall()

        transactions = conn.execute("""
            SELECT transaction_type, amount
            FROM transactions t
            JOIN accounts a ON t.account_id = a.account_id
            WHERE a.customer_id = ?
            ORDER BY transaction_date DESC
            LIMIT 5
        """, (customer_id,)).fetchall()

        return {
            "customer": dict(overview),
            "recent_interactions": [dict(i) for i in interactions],
            "recent_transactions": [dict(t) for t in transactions]
        }
    finally:
        conn.close()


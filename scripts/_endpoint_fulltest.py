"""Ad-hoc full endpoint test harness (Gemini-backed). Not part of the app.

Runs every REST endpoint with realistic inputs, prints a readable Q&A log,
and collects any issues (non-2xx, exceptions, empty/slow answers).
"""
from __future__ import annotations

import json
import time
import httpx

BASE = "http://127.0.0.1:8000"
V1 = f"{BASE}/api/v1"
CID = "CUST-1001"
SESSION = "gemini-test-001"

issues: list[str] = []
results: list[dict] = []


def _short(obj, n=600):
    try:
        s = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False, default=str)
    except Exception:
        s = str(obj)
    return s if len(s) <= n else s[:n] + f"  …(+{len(s)-n} chars)"


def call(method, url, *, label, json_body=None, expect=200, timeout=120.0):
    print("\n" + "=" * 90)
    print(f"[{label}] {method} {url}")
    if json_body is not None:
        print(f"  REQUEST: {_short(json_body)}")
    t0 = time.time()
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.request(method, url, json=json_body)
        dt = time.time() - t0
        ctype = r.headers.get("content-type", "")
        body = r.json() if "application/json" in ctype else r.text
        print(f"  STATUS: {r.status_code}   ({dt:.1f}s)")
        print(f"  RESPONSE: {_short(body)}")
        ok = (r.status_code == expect)
        if not ok:
            issues.append(f"[{label}] expected {expect}, got {r.status_code}: {_short(body,200)}")
        if dt > 30:
            issues.append(f"[{label}] slow response: {dt:.1f}s")
        results.append({"label": label, "status": r.status_code, "seconds": round(dt, 1)})
        return body
    except Exception as e:
        dt = time.time() - t0
        print(f"  ERROR after {dt:.1f}s: {type(e).__name__}: {e}")
        issues.append(f"[{label}] EXCEPTION: {type(e).__name__}: {e}")
        results.append({"label": label, "status": "EXC", "seconds": round(dt, 1)})
        return None


def chat(message, *, label, client_id=CID, session=SESSION):
    return call(
        "POST", f"{V1}/agent/chat", label=label,
        json_body={"message": message, "session_id": session,
                   "metadata": {"client_id": client_id}},
        timeout=240.0,
    )


def main():
    # ---- System ----
    call("GET", f"{BASE}/health", label="health")
    call("GET", f"{V1}/agent/info", label="agent/info")

    # ---- Static data endpoints (deterministic, no LLM) ----
    call("GET", f"{V1}/agent/clients", label="agent/clients")
    call("GET", f"{V1}/crm/", label="crm/list")
    call("GET", f"{V1}/crm/{CID}", label="crm/profile")
    call("GET", f"{V1}/crm/{CID}/interactions?limit=3", label="crm/interactions")
    call("GET", f"{V1}/crm/{CID}/advisory", label="crm/advisory")
    call("GET", f"{V1}/portfolio/", label="portfolio/list")
    call("GET", f"{V1}/portfolio/{CID}", label="portfolio/snapshot")
    call("GET", f"{V1}/portfolio/{CID}/performance", label="portfolio/performance")
    call("GET", f"{V1}/portfolio/{CID}/compliance", label="portfolio/compliance")

    # ---- Error / edge cases ----
    call("GET", f"{V1}/crm/CUST-9999", label="crm/notfound", expect=404)
    call("GET", f"{V1}/portfolio/CUST-9999", label="portfolio/notfound", expect=404)
    call("POST", f"{V1}/agent/chat", label="chat/empty-msg", expect=422,
         json_body={"message": "   ", "session_id": SESSION})
    call("POST", f"{V1}/agent/chat", label="chat/bad-session", expect=422,
         json_body={"message": "hi", "session_id": "bad session!!"})

    # ---- Agent chat (LLM / Gemini) — realistic RM queries ----
    chat("Hello, what can you help me with?", label="chat/greeting")
    chat(f"Give me a portfolio summary for {CID}.", label="chat/portfolio")
    chat(f"What were my recent interactions and any open service requests for {CID}?",
         label="chat/crm")
    chat(f"For {CID}, combine the portfolio performance with recent client sentiment "
         f"and suggest next best actions.", label="chat/both")
    chat("What is the capital of France?", label="chat/out-of-scope")
    chat("Compare it against last quarter.", label="chat/followup")  # tests memory/context

    # ---- Session retrieval ----
    call("GET", f"{V1}/agent/sessions", label="agent/sessions")
    call("GET", f"{V1}/agent/sessions/{SESSION}", label="agent/session-history")

    # ---- Summary ----
    print("\n" + "#" * 90)
    print("RESULT SUMMARY")
    for r in results:
        print(f"  {r['status']:>6}  {r['seconds']:>5}s  {r['label']}")
    print("\nISSUES FOUND:" if issues else "\nNO ISSUES FOUND.")
    for i in issues:
        print(f"  - {i}")


if __name__ == "__main__":
    main()

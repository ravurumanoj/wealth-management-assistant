"""Temporary endpoint smoke test — hits every route with real queries and prints Q&A."""
import json
import time
import httpx

BASE = "http://127.0.0.1:8000"
API = f"{BASE}/api/v1"
CID = "CUST-1001"

results = []


def show(title, method, url, resp, note=""):
    line = "=" * 90
    print(f"\n{line}\n[{method}] {title}\n{url}\nHTTP {resp.status_code}  {note}")
    try:
        body = resp.json()
        text = json.dumps(body, indent=2, ensure_ascii=False)
    except Exception:
        text = resp.text
    if len(text) > 1600:
        text = text[:1600] + "\n... [truncated] ..."
    print(text)
    results.append((title, resp.status_code))


def chat(question, session, client_id=CID):
    payload = {"message": question, "session_id": session, "metadata": {"client_id": client_id}}
    t0 = time.time()
    try:
        r = httpx.post(f"{API}/agent/chat", json=payload, timeout=120)
        dt = f"{time.time()-t0:.1f}s"
        print("\n" + "#" * 90)
        print(f"Q ({client_id}): {question}")
        try:
            data = r.json()
            print(f"agent_used: {data.get('agent_used')}  |  HTTP {r.status_code}  |  {dt}")
            print(f"A: {data.get('response')}")
        except Exception:
            print(f"HTTP {r.status_code} (non-JSON): {r.text[:800]}")
        results.append((f"chat: {question[:40]}", r.status_code))
    except Exception as e:
        print(f"\nQ: {question}\nERROR: {e}")
        results.append((f"chat: {question[:40]}", "ERR"))


def main():
    with httpx.Client() as c:
        show("Health", "GET", f"{BASE}/health", c.get(f"{BASE}/health"))
        show("Agent info", "GET", f"{API}/agent/info", c.get(f"{API}/agent/info"))
        show("List clients", "GET", f"{API}/agent/clients", c.get(f"{API}/agent/clients"))

        # Portfolio
        show("Portfolio summary (all)", "GET", f"{API}/portfolio/", c.get(f"{API}/portfolio/"))
        show("Portfolio snapshot", "GET", f"{API}/portfolio/{CID}", c.get(f"{API}/portfolio/{CID}"))
        show("Portfolio performance", "GET", f"{API}/portfolio/{CID}/performance", c.get(f"{API}/portfolio/{CID}/performance"))
        show("Portfolio compliance", "GET", f"{API}/portfolio/{CID}/compliance", c.get(f"{API}/portfolio/{CID}/compliance"))
        show("Portfolio 404", "GET", f"{API}/portfolio/CUST-9999", c.get(f"{API}/portfolio/CUST-9999"), note="(expect 404)")

        # CRM
        show("CRM summary (all)", "GET", f"{API}/crm/", c.get(f"{API}/crm/"))
        show("CRM profile", "GET", f"{API}/crm/{CID}", c.get(f"{API}/crm/{CID}"))
        show("CRM interactions", "GET", f"{API}/crm/{CID}/interactions?limit=3", c.get(f"{API}/crm/{CID}/interactions?limit=3"))
        show("CRM advisory", "GET", f"{API}/crm/{CID}/advisory", c.get(f"{API}/crm/{CID}/advisory"))
        show("CRM 404", "GET", f"{API}/crm/CUST-9999", c.get(f"{API}/crm/CUST-9999"), note="(expect 404)")

    # Agent chat — real queries across intents
    chat("What is the current asset allocation and total value of my portfolio?", "sess-portfolio")
    chat("How has the portfolio performed and what is the P&L?", "sess-portfolio")
    chat("Summarize recent client interactions and their sentiment.", "sess-crm")
    chat("What advisory actions or compliance flags should I know about?", "sess-crm")
    chat("Hello, what can you help me with?", "sess-general")
    chat("Tell me about it", "sess-clarify")  # ambiguous -> clarification

    print("\n" + "=" * 90)
    print("SUMMARY")
    for name, code in results:
        print(f"  {code}\t{name}")


if __name__ == "__main__":
    main()

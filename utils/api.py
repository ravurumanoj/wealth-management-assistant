import requests


def call_backend(user_message: str, endpoint: str, api_key: str = "", payload_builder=None) -> str:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = payload_builder(user_message) if payload_builder else {"message": user_message}
    response = requests.post(endpoint, json=payload, headers=headers, timeout=90)
    response.raise_for_status()
    data = response.json()

    if isinstance(data, dict):
        for key in ["answer", "response", "message", "content", "output"]:
            if key in data and isinstance(data[key], str):
                return data[key]

        if "choices" in data and data["choices"]:
            first = data["choices"][0]
            if isinstance(first, dict):
                return first.get("message", {}).get("content") or first.get("text", "")

    return "I received a response from the backend, but I couldn't find a displayable answer field."
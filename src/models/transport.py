"""JSON transport shared by explicitly configured model endpoints."""

from urllib.parse import urlsplit

import requests


def post_json(base_url: str, path: str, payload: dict, api_key: str | None) -> dict:
    parsed = urlsplit(base_url)
    if parsed.username or parsed.password or parsed.query or parsed.fragment or not parsed.hostname:
        raise ValueError("Use a base URL without credentials, query parameters or fragments")
    if parsed.scheme != "https" and not (
        parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    ):
        raise ValueError("Model endpoints require HTTPS, except loopback development servers")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    response = requests.post(base_url.rstrip('/') + '/' + path, json=payload,
                             headers=headers, timeout=60, allow_redirects=False)
    if response.status_code != 200:
        raise RuntimeError(f"Model endpoint returned HTTP {response.status_code}")
    result = response.json()
    if not isinstance(result, dict) or result.get("error"):
        raise ValueError("Model endpoint did not return a successful JSON object")
    return result

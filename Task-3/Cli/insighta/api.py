import httpx
import typer
from insighta.store import get_tokens, save_tokens, clear_tokens

BASE_URL = os.environ.get("INSIGHTA_API_URL", "http://localhost:8000")


def _refresh_tokens() -> str | None:
    tokens = get_tokens()
    if not tokens or not tokens.get("refresh_token"):
        return None

    res = httpx.post(
        f"{BASE_URL}/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )

    if res.status_code != 200:
        clear_tokens()
        return None

    data = res.json()
    save_tokens(data["access_token"], data["refresh_token"])
    return data["access_token"]


def api_request(method: str, path: str, **kwargs) -> httpx.Response:
    tokens = get_tokens()
    if not tokens or not tokens.get("access_token"):
        typer.echo("Not logged in. Run: insighta login")
        raise typer.Exit(1)

    headers = {
        "Authorization": f"Bearer {tokens['access_token']}",
        "X-API-Version": "3",
        "Content-Type": "application/json",
    }

    res = httpx.request(method, f"{BASE_URL}{path}", headers=headers, **kwargs)

    # Auto-refresh on 401
    if res.status_code == 401:
        new_token = _refresh_tokens()
        if not new_token:
            typer.echo("Session expired. Please run: insighta login")
            raise typer.Exit(1)
        headers["Authorization"] = f"Bearer {new_token}"
        res = httpx.request(method, f"{BASE_URL}{path}", headers=headers, **kwargs)

    return res


import os  # noqa: E402 (needed for BASE_URL above)
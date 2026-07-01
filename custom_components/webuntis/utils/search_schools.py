import time
import requests
from webuntis import errors
import json

def search_schools(query: str) -> dict:
    """Search for schools using the WebUntis school search API."""

    url = "https://schoolsearch.webuntis.com/schoolquery2"

    payload = {
        "id": f"wu_schulsuche-{int(time.time() * 1000)}",
        "method": "searchSchool",
        "params": [{"search": query}],
        "jsonrpc": "2.0",
    }

    headers = {
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()

    except requests.RequestException as exc:
        raise errors.RemoteError(
            f"School search request failed: {exc}"
        ) from exc

    try:
        data = response.json()

    except json.JSONDecodeError as exc:
        raise errors.RemoteError(
            "Invalid JSON response from school search"
        ) from exc

    schools = []

    for school in data.get("result", {}).get("schools", []):
        schools.append(
            {
                "name": school.get("displayName"),
                "login_name": school.get("loginName"),
                "school_id": school.get("schoolId"),
                "address": school.get("address"),
                "server": school.get("server"),
                "server_url": school.get("serverUrl"),
            }
        )

    return {
        "query": query,
        "count": len(schools),
        "schools": schools,
    }
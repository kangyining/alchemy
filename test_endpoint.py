#!/usr/bin/env python3
"""Test script for ADK Cloud Run endpoints.

Usage:
    python test_endpoint.py

Requires:
    - gcloud CLI authenticated
    - requests library (pip install requests)
"""

import json
import subprocess
import sys
from typing import Any

try:
    import requests
except ImportError:
    print("ERROR: requests library not installed. Run: pip install requests")
    sys.exit(1)


# =============================================================================
# CONFIGURATION
# =============================================================================

BASE_URL = "https://report-agents-447504735658.us-central1.run.app"
APP_NAME = "report_agents"
USER_ID = "test_user"
SESSION_ID = "test_session"


# =============================================================================
# HELPERS
# =============================================================================

def get_identity_token() -> str:
    """Get GCP identity token for authentication."""
    result = subprocess.run(
        ["gcloud", "auth", "print-identity-token"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"ERROR: Failed to get identity token: {result.stderr}")
        print("Run: gcloud auth login")
        sys.exit(1)
    return result.stdout.strip()


def make_request(
    method: str,
    path: str,
    token: str,
    data: dict | None = None,
) -> requests.Response:
    """Make authenticated request to the API."""
    url = f"{BASE_URL}{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    
    if method == "GET":
        return requests.get(url, headers=headers)
    elif method == "POST":
        return requests.post(url, headers=headers, json=data or {})
    else:
        raise ValueError(f"Unsupported method: {method}")


def print_response(name: str, response: requests.Response) -> None:
    """Pretty print response."""
    print(f"\n{'='*60}")
    print(f"{name}")
    print(f"{'='*60}")
    print(f"Status: {response.status_code}")
    try:
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except Exception:
        print(f"Response: {response.text[:500]}")


# =============================================================================
# TEST FUNCTIONS
# =============================================================================

def test_list_apps(token: str) -> bool:
    """Test: List available apps."""
    response = make_request("GET", "/list-apps", token)
    print_response("GET /list-apps", response)
    return response.status_code == 200


def test_create_session(token: str) -> bool:
    """Test: Create a new session."""
    path = f"/apps/{APP_NAME}/users/{USER_ID}/sessions/{SESSION_ID}"
    response = make_request("POST", path, token, data={})
    print_response(f"POST {path}", response)
    return response.status_code == 200


def test_get_session(token: str) -> bool:
    """Test: Get session details."""
    path = f"/apps/{APP_NAME}/users/{USER_ID}/sessions/{SESSION_ID}"
    response = make_request("GET", path, token)
    print_response(f"GET {path}", response)
    return response.status_code == 200


def test_run_agent(token: str, message: str = "Hello, are you working?") -> bool:
    """Test: Run the agent with a message."""
    data = {
        "app_name": APP_NAME,
        "user_id": USER_ID,
        "session_id": SESSION_ID,
        "new_message": {
            "role": "user",
            "parts": [{"text": message}],
        },
        "streaming": False,
    }
    response = make_request("POST", "/run_sse", token, data=data)
    print_response("POST /run_sse", response)
    return response.status_code == 200


def test_list_artifacts(token: str) -> bool:
    """Test: List artifacts for a session."""
    path = f"/apps/{APP_NAME}/users/{USER_ID}/sessions/{SESSION_ID}/artifacts"
    response = make_request("GET", path, token)
    print_response(f"GET {path}", response)
    # May return 404 if no artifacts exist yet
    return response.status_code in (200, 404)


def test_delete_session(token: str) -> bool:
    """Test: Delete a session."""
    path = f"/apps/{APP_NAME}/users/{USER_ID}/sessions/{SESSION_ID}"
    url = f"{BASE_URL}{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    response = requests.delete(url, headers=headers)
    print_response(f"DELETE {path}", response)
    return response.status_code in (200, 204, 404)


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("ADK Cloud Run Endpoint Test")
    print(f"Base URL: {BASE_URL}")
    print(f"App: {APP_NAME}")
    
    # Get auth token
    print("\nGetting identity token...")
    token = get_identity_token()
    print("✓ Token obtained")
    
    # Run tests
    results = {}
    
    results["list_apps"] = test_list_apps(token)
    results["create_session"] = test_create_session(token)
    results["get_session"] = test_get_session(token)
    results["run_agent"] = test_run_agent(token)
    results["list_artifacts"] = test_list_artifacts(token)
    # Uncomment to test deletion:
    # results["delete_session"] = test_delete_session(token)
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {name}: {status}")
    
    all_passed = all(results.values())
    print(f"\nOverall: {'✓ All tests passed' if all_passed else '✗ Some tests failed'}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())

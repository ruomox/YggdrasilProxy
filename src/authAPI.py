# src/authAPI.py
import requests
import uuid
from src import constants

TIMEOUT_SETTINGS = (5, 10)


def get_fallback_client_token():
    return str(uuid.uuid4())


def authenticate(auth_url, email, password, client_token=None):
    if not client_token:
        client_token = get_fallback_client_token()

    payload = {
        "agent": constants.AUTH_AGENT,
        "username": email,
        "password": password,
        "requestUser": True,
        "clientToken": client_token
    }

    try:
        resp = requests.post(auth_url, json=payload, headers={"Content-Type": "application/json"},
                             timeout=TIMEOUT_SETTINGS)
        resp.raise_for_status()
        data = resp.json()
        if "clientToken" not in data or not data["clientToken"]:
            data["clientToken"] = client_token
        return data
    except Exception as e:
        if isinstance(e, requests.exceptions.HTTPError):
            print(f"[Auth Login Error] {e.response.status_code}: {e.response.text}")
        raise e


def refresh(refresh_url, access_token, client_token, selected_profile=None):
    """
    刷新接口 (支持绑定角色)
    selected_profile: {"id": "...", "name": "..."}
    """
    if not client_token:
        client_token = get_fallback_client_token()

    payload = {
        "accessToken": access_token,
        "clientToken": client_token,
        "requestUser": True
    }

    # 【关键修改】如果传入了角色信息，请求绑定该角色
    if selected_profile:
        payload["selectedProfile"] = selected_profile

    try:
        resp = requests.post(refresh_url, json=payload, headers={"Content-Type": "application/json"},
                             timeout=TIMEOUT_SETTINGS)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        if isinstance(e, requests.exceptions.HTTPError):
            print(f"[Auth Refresh Error] {e.response.status_code}: {e.response.text}")
        raise e


def validate(validate_url, access_token, client_token):
    if not client_token: return False
    payload = {"accessToken": access_token, "clientToken": client_token}
    try:
        resp = requests.post(validate_url, json=payload, headers={"Content-Type": "application/json"}, timeout=5)
        return resp.status_code == 204
    except Exception:
        return False
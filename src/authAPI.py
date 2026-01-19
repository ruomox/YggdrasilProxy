# src/authAPI.py
import requests
from src import constants

# 设置较短的连接超时，较长的读取超时
TIMEOUT_SETTINGS = (5, 15)

def authenticate(auth_url, email, password, client_token=None):
    payload = {
        "agent": constants.AUTH_AGENT,
        "username": email,
        "password": password,
        "requestUser": True,
        "clientToken": client_token
    }
    resp = requests.post(auth_url, json=payload, headers={"Content-Type": "application/json"}, timeout=TIMEOUT_SETTINGS)
    resp.raise_for_status()
    return resp.json()

def refresh(refresh_url, access_token, client_token):
    payload = {"accessToken": access_token, "clientToken": client_token, "requestUser": True}
    resp = requests.post(refresh_url, json=payload, headers={"Content-Type": "application/json"}, timeout=TIMEOUT_SETTINGS)
    resp.raise_for_status()
    return resp.json()

def validate(validate_url, access_token, client_token):
    payload = {"accessToken": access_token, "clientToken": client_token}
    try:
        resp = requests.post(validate_url, json=payload, headers={"Content-Type": "application/json"}, timeout=5)
        return resp.status_code == 204
    except Exception:
        return False
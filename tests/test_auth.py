"""Tests for the authentication & verification flow."""
from app.modules.users.repository import UserRepository

API = "/api/v1"


async def _signup(client, email="user@example.com", password="Password123"):
    return await client.post(
        f"{API}/auth/signup",
        json={"email": email, "password": password, "first_name": "Ada"},
    )


async def _get_code(session_factory, email):
    async with session_factory() as session:
        user = await UserRepository(session).get_by_email(email)
        return user.verification_code


async def test_signup_creates_unverified_user(client):
    resp = await _signup(client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["user"]["email"] == "user@example.com"
    assert body["user"]["is_verified"] is False
    assert body["user"]["role"] == "user"


async def test_signup_duplicate_email_conflicts(client):
    await _signup(client)
    resp = await _signup(client)
    assert resp.status_code == 409


async def test_login_and_refresh(client):
    await _signup(client)
    login = await client.post(
        f"{API}/auth/login",
        json={"email": "user@example.com", "password": "Password123"},
    )
    assert login.status_code == 200
    tokens = login.json()
    assert tokens["access_token"] and tokens["refresh_token"]

    refresh = await client.post(
        f"{API}/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh.status_code == 200
    assert refresh.json()["access_token"]


async def test_login_wrong_password_rejected(client):
    await _signup(client)
    resp = await client.post(
        f"{API}/auth/login",
        json={"email": "user@example.com", "password": "wrong"},
    )
    assert resp.status_code == 401


async def test_verify_flow(client, session_factory):
    await _signup(client)
    code = await _get_code(session_factory, "user@example.com")

    resp = await client.post(
        f"{API}/auth/verify",
        json={"email": "user@example.com", "code": code},
    )
    assert resp.status_code == 200
    assert resp.json()["is_verified"] is True


async def test_verify_wrong_code_rejected(client):
    await _signup(client)
    resp = await client.post(
        f"{API}/auth/verify",
        json={"email": "user@example.com", "code": "000000"},
    )
    assert resp.status_code == 422


async def test_me_requires_authentication(client):
    resp = await client.get(f"{API}/me")
    assert resp.status_code == 401


async def test_me_returns_current_user(client):
    await _signup(client)
    login = await client.post(
        f"{API}/auth/login",
        json={"email": "user@example.com", "password": "Password123"},
    )
    token = login.json()["access_token"]
    resp = await client.get(
        f"{API}/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == "user@example.com"

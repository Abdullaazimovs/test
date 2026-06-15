"""Tests for role-based user management endpoints."""
from app.core.security import hash_password
from app.modules.users.models import User, UserRole

API = "/api/v1"


async def _make_user(session_factory, email, role=UserRole.USER, password="Password123"):
    async with session_factory() as session:
        user = User(
            email=email,
            hashed_password=hash_password(password),
            role=role,
            is_active=True,
            is_verified=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user.id


async def _token(client, email, password="Password123"):
    resp = await client.post(
        f"{API}/auth/login", json={"email": email, "password": password}
    )
    return resp.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


async def test_list_users_forbidden_for_regular_user(client, session_factory):
    await _make_user(session_factory, "user@example.com")
    token = await _token(client, "user@example.com")
    resp = await client.get(f"{API}/users", headers=_auth(token))
    assert resp.status_code == 403


async def test_list_users_allowed_for_admin(client, session_factory):
    await _make_user(session_factory, "admin@example.com", role=UserRole.ADMIN)
    await _make_user(session_factory, "user@example.com")
    token = await _token(client, "admin@example.com")
    resp = await client.get(f"{API}/users", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["total"] == 2


async def test_get_user_by_id_admin_only(client, session_factory):
    await _make_user(session_factory, "admin@example.com", role=UserRole.ADMIN)
    target = await _make_user(session_factory, "user@example.com")
    token = await _token(client, "admin@example.com")
    resp = await client.get(f"{API}/users/{target}", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["email"] == "user@example.com"


async def test_user_can_update_own_profile(client, session_factory):
    uid = await _make_user(session_factory, "user@example.com")
    token = await _token(client, "user@example.com")
    resp = await client.patch(
        f"{API}/users/{uid}",
        headers=_auth(token),
        json={"first_name": "Grace"},
    )
    assert resp.status_code == 200
    assert resp.json()["first_name"] == "Grace"


async def test_user_cannot_change_role(client, session_factory):
    uid = await _make_user(session_factory, "user@example.com")
    token = await _token(client, "user@example.com")
    resp = await client.patch(
        f"{API}/users/{uid}",
        headers=_auth(token),
        json={"role": "admin"},
    )
    assert resp.status_code == 403


async def test_user_cannot_update_other_user(client, session_factory):
    other = await _make_user(session_factory, "other@example.com")
    await _make_user(session_factory, "user@example.com")
    token = await _token(client, "user@example.com")
    resp = await client.patch(
        f"{API}/users/{other}",
        headers=_auth(token),
        json={"first_name": "Nope"},
    )
    assert resp.status_code == 403


async def test_admin_can_delete_user(client, session_factory):
    await _make_user(session_factory, "admin@example.com", role=UserRole.ADMIN)
    target = await _make_user(session_factory, "user@example.com")
    token = await _token(client, "admin@example.com")
    resp = await client.delete(f"{API}/users/{target}", headers=_auth(token))
    assert resp.status_code == 204

    # Confirm it is gone.
    follow = await client.get(f"{API}/users/{target}", headers=_auth(token))
    assert follow.status_code == 404


async def test_regular_user_cannot_delete(client, session_factory):
    target = await _make_user(session_factory, "user@example.com")
    token = await _token(client, "user@example.com")
    resp = await client.delete(f"{API}/users/{target}", headers=_auth(token))
    assert resp.status_code == 403

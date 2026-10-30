import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.organizations.models import Membership, Organization

pytestmark = pytest.mark.django_db

PASSWORD = "Str0ng!Pass#2026"
User = get_user_model()


def register(client, username, org_name):
    return client.post(
        "/api/auth/register/",
        {
            "username": username,
            "email": f"{username}@example.com",
            "password": PASSWORD,
            "organization_name": org_name,
        },
        format="json",
    )


def login(client, username):
    response = client.post(
        "/api/auth/login/", {"username": username, "password": PASSWORD}, format="json"
    )
    assert response.status_code == 200
    return response.json()


def logged_in_client(username, org_name=None):
    client = APIClient()
    if org_name:
        register(client, username, org_name)
    tokens = login(client, username)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    return client


def test_register_creates_user_organization_and_owner():
    response = register(APIClient(), "alice", "Acme Corp")

    assert response.status_code == 201
    membership = Membership.objects.get(user__username="alice")
    assert membership.role == Membership.Role.OWNER
    assert membership.organization.name == "Acme Corp"


def test_weak_password_is_rejected():
    response = APIClient().post(
        "/api/auth/register/",
        {
            "username": "bob",
            "email": "bob@example.com",
            "password": "12345",
            "organization_name": "Bob Inc",
        },
        format="json",
    )
    assert response.status_code == 400
    assert "password" in response.json()


def test_protected_endpoint_needs_a_token():
    assert APIClient().get("/api/auth/me/").status_code == 401


def test_me_returns_memberships():
    client = logged_in_client("alice", "Acme Corp")
    data = client.get("/api/auth/me/").json()

    assert data["username"] == "alice"
    assert data["memberships"][0]["role"] == "owner"


def test_logout_blacklists_refresh_token():
    client = APIClient()
    register(client, "alice", "Acme Corp")
    refresh = login(client, "alice")["refresh"]

    assert client.post("/api/auth/logout/", {"refresh": refresh}, format="json").status_code == 200
    assert client.post("/api/auth/refresh/", {"refresh": refresh}, format="json").status_code == 401


def test_plain_member_cannot_list_members():
    register(APIClient(), "alice", "Acme Corp")
    org = Organization.objects.get(name="Acme Corp")
    carol = User.objects.create_user(username="carol", password=PASSWORD)
    Membership.objects.create(user=carol, organization=org, role=Membership.Role.MEMBER)

    client = logged_in_client("carol")
    header = {"HTTP_X_ORGANIZATION_ID": str(org.id)}

    assert client.get("/api/org/", **header).status_code == 200
    assert client.get("/api/org/members/", **header).status_code == 403


def test_user_cannot_use_another_organizations_id():
    register(APIClient(), "alice", "Acme Corp")
    acme = Organization.objects.get(name="Acme Corp")
    bob = logged_in_client("bob", "Bob Inc")

    response = bob.get("/api/org/", HTTP_X_ORGANIZATION_ID=str(acme.id))

    assert response.status_code == 403

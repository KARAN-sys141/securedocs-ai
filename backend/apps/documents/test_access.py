import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.documents.access import visible_chunks
from apps.documents.models import Chunk, Document, DocumentAccess
from apps.organizations.models import Membership, Organization

pytestmark = pytest.mark.django_db

PASSWORD = "Str0ng!Pass#2026"
User = get_user_model()


def make_user(username, org, role):
    user = User.objects.create_user(
        username=username, email=f"{username}@example.com", password=PASSWORD
    )
    Membership.objects.create(user=user, organization=org, role=role)
    return user


def client_for(username, org):
    client = APIClient()
    response = client.post(
        "/api/auth/login/", {"username": username, "password": PASSWORD}, format="json"
    )
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {response.json()['access']}",
        HTTP_X_ORGANIZATION_ID=str(org.id),
    )
    return client


def make_doc(org, title, visibility, uploaded_by):
    return Document.objects.create(
        organization=org,
        title=title,
        original_filename=f"{title}.pdf",
        visibility=visibility,
        uploaded_by=uploaded_by,
    )


def titles(response):
    return {d["title"] for d in response.json()}


@pytest.fixture
def world():
    acme = Organization.objects.create(name="Acme", slug="acme")
    other = Organization.objects.create(name="Other", slug="other")
    owner = make_user("olivia", acme, Membership.Role.OWNER)
    admin = make_user("adam", acme, Membership.Role.ADMIN)
    bob = make_user("bob", acme, Membership.Role.MEMBER)
    carol = make_user("carol", acme, Membership.Role.MEMBER)
    eve = make_user("eve", other, Membership.Role.OWNER)
    org_wide = Document.Visibility.ORGANIZATION
    restricted = Document.Visibility.RESTRICTED
    return {
        "acme": acme,
        "other": other,
        "owner": owner,
        "admin": admin,
        "bob": bob,
        "carol": carol,
        "eve": eve,
        "handbook": make_doc(acme, "Handbook", org_wide, owner),
        "salaries": make_doc(acme, "Salaries", restricted, owner),
        "carol_notes": make_doc(acme, "Carol notes", restricted, carol),
        "eve_plan": make_doc(other, "Eve plan", org_wide, eve),
    }


def test_member_sees_only_organization_wide_documents(world):
    client = client_for("bob", world["acme"])
    assert titles(client.get("/api/documents/")) == {"Handbook"}


def test_owner_and_admin_see_restricted_documents(world):
    for name in ("olivia", "adam"):
        client = client_for(name, world["acme"])
        expected = {"Handbook", "Salaries", "Carol notes"}
        assert titles(client.get("/api/documents/")) == expected


def test_uploader_sees_own_restricted_document(world):
    client = client_for("carol", world["acme"])
    assert titles(client.get("/api/documents/")) == {"Handbook", "Carol notes"}


def test_grant_makes_document_visible_and_revoke_hides_it(world):
    owner = client_for("olivia", world["acme"])
    bob = client_for("bob", world["acme"])
    doc_id = world["salaries"].id
    bob_id = world["bob"].id

    assert bob.get(f"/api/documents/{doc_id}/").status_code == 404

    response = owner.post(f"/api/documents/{doc_id}/access/", {"user_id": bob_id}, format="json")
    assert response.status_code == 201
    assert bob.get(f"/api/documents/{doc_id}/").status_code == 200

    assert owner.delete(f"/api/documents/{doc_id}/access/{bob_id}/").status_code == 204
    assert bob.get(f"/api/documents/{doc_id}/").status_code == 404


def test_other_organization_cannot_see_documents(world):
    eve = client_for("eve", world["other"])
    handbook_id = world["handbook"].id

    assert eve.get(f"/api/documents/{handbook_id}/").status_code == 404
    assert titles(eve.get("/api/documents/")) == {"Eve plan"}

    # Using Acme's id with Eve's token must be refused outright.
    spoof = client_for("eve", world["acme"])
    assert spoof.get("/api/documents/").status_code == 403


def test_plain_member_cannot_manage_access(world):
    bob = client_for("bob", world["acme"])
    doc_id = world["handbook"].id
    carol_id = world["carol"].id

    response = bob.post(f"/api/documents/{doc_id}/access/", {"user_id": carol_id}, format="json")
    assert response.status_code == 403


def test_cannot_grant_access_to_user_outside_the_organization(world):
    owner = client_for("olivia", world["acme"])
    doc_id = world["salaries"].id
    eve_id = world["eve"].id

    response = owner.post(f"/api/documents/{doc_id}/access/", {"user_id": eve_id}, format="json")
    assert response.status_code == 400


def test_owner_can_add_existing_user_by_email(world):
    owner = client_for("olivia", world["acme"])
    response = owner.post("/api/org/members/", {"email": "eve@example.com"}, format="json")

    assert response.status_code == 201
    assert Membership.objects.filter(user=world["eve"], organization=world["acme"]).exists()


def test_admin_cannot_promote_member_but_owner_can(world):
    admin = client_for("adam", world["acme"])
    owner = client_for("olivia", world["acme"])
    url = f"/api/org/members/{world['bob'].id}/"

    assert admin.patch(url, {"role": "admin"}, format="json").status_code == 403
    assert owner.patch(url, {"role": "admin"}, format="json").status_code == 200
    assert Membership.objects.get(user=world["bob"]).role == "admin"


def test_admin_cannot_remove_another_admin(world):
    Membership.objects.filter(user=world["carol"]).update(role=Membership.Role.ADMIN)
    admin = client_for("adam", world["acme"])

    response = admin.delete(f"/api/org/members/{world['carol'].id}/")
    assert response.status_code == 403


def test_nobody_can_change_their_own_membership(world):
    owner = client_for("olivia", world["acme"])
    url = f"/api/org/members/{world['owner'].id}/"

    assert owner.patch(url, {"role": "member"}, format="json").status_code == 403


def test_removing_a_member_also_removes_their_document_grants(world):
    DocumentAccess.objects.create(document=world["salaries"], user=world["bob"])
    owner = client_for("olivia", world["acme"])

    assert owner.delete(f"/api/org/members/{world['bob'].id}/").status_code == 204
    assert not DocumentAccess.objects.filter(user=world["bob"]).exists()
    assert not Membership.objects.filter(user=world["bob"]).exists()


def test_search_scope_excludes_restricted_chunks(world):
    Chunk.objects.create(document=world["handbook"], chunk_index=0, content="public text")
    Chunk.objects.create(document=world["salaries"], chunk_index=0, content="secret salaries")
    bob_membership = Membership.objects.get(user=world["bob"])

    contents = set(visible_chunks(bob_membership).values_list("content", flat=True))
    assert contents == {"public text"}

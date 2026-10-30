import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from apps.organizations.models import Membership, Organization

pytestmark = pytest.mark.django_db


def test_user_can_join_an_organization_only_once():
    user = get_user_model().objects.create_user(username="alice", password="pass12345")
    org = Organization.objects.create(name="Acme", slug="acme")
    Membership.objects.create(user=user, organization=org, role=Membership.Role.ADMIN)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Membership.objects.create(user=user, organization=org)

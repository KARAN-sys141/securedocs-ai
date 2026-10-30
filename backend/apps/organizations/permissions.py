from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission

from .models import Membership

ORG_HEADER = "X-Organization-ID"
NOT_A_MEMBER = "You are not a member of this organization."


def resolve_membership(request):
    """Find which organization this request is for and the user's role in it."""
    memberships = Membership.objects.select_related("organization").filter(user=request.user)
    org_id = request.headers.get(ORG_HEADER)

    if org_id:
        try:
            return memberships.get(organization_id=org_id)
        except (Membership.DoesNotExist, DjangoValidationError, ValueError) as exc:
            # Same message for "does not exist" and "not yours" on purpose.
            raise PermissionDenied(NOT_A_MEMBER) from exc

    found = list(memberships[:2])
    if not found:
        raise PermissionDenied("You do not belong to any organization.")
    if len(found) > 1:
        raise ValidationError(f"You belong to several organizations. Send the {ORG_HEADER} header.")
    return found[0]


class IsOrganizationMember(BasePermission):
    """Allows any member. Sets request.organization and request.membership."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        membership = resolve_membership(request)
        request.membership = membership
        request.organization = membership.organization
        return True


class IsOrganizationAdmin(IsOrganizationMember):
    """Allows only owners and admins of the organization."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return request.membership.role in (Membership.Role.OWNER, Membership.Role.ADMIN)

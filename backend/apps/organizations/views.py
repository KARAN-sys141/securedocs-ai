from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.documents.models import DocumentAccess

from .models import Membership
from .permissions import IsOrganizationAdmin, IsOrganizationMember
from .serializers import AddMemberSerializer, RoleSerializer

User = get_user_model()


def member_data(membership):
    return {
        "user_id": membership.user_id,
        "username": membership.user.username,
        "email": membership.user.email,
        "role": membership.role,
    }


def check_can_manage(actor, target, new_role=None):
    """Nobody edits themselves. Owners manage anyone. Admins manage only members."""
    if actor.user_id == target.user_id:
        raise PermissionDenied("You cannot change your own membership.")
    if actor.role == Membership.Role.OWNER:
        return
    if target.role != Membership.Role.MEMBER:
        raise PermissionDenied("Admins can only manage regular members.")
    if new_role and new_role != Membership.Role.MEMBER:
        raise PermissionDenied("Only owners can give the admin or owner role.")


class CurrentOrganizationView(APIView):
    """Any member can see basic info about the current organization."""

    permission_classes = [IsAuthenticated, IsOrganizationMember]

    def get(self, request):
        org = request.organization
        return Response(
            {
                "id": org.id,
                "name": org.name,
                "slug": org.slug,
                "your_role": request.membership.role,
            }
        )


class MemberListView(APIView):
    """Owners and admins can list members and add existing users by email."""

    permission_classes = [IsAuthenticated, IsOrganizationAdmin]

    def get(self, request):
        members = Membership.objects.filter(organization=request.organization).select_related(
            "user"
        )
        return Response([member_data(m) for m in members])

    def post(self, request):
        serializer = AddMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = serializer.validated_data["role"]

        if request.membership.role != Membership.Role.OWNER and role != Membership.Role.MEMBER:
            raise PermissionDenied("Admins can only add regular members.")

        user = User.objects.filter(email__iexact=serializer.validated_data["email"]).first()
        if user is None:
            raise ValidationError({"email": "No registered user has this email."})

        membership, created = Membership.objects.get_or_create(
            user=user, organization=request.organization, defaults={"role": role}
        )
        if not created:
            raise ValidationError({"email": "This user is already a member."})
        return Response(member_data(membership), status=status.HTTP_201_CREATED)


class MemberDetailView(APIView):
    """Change the role of a member, or remove them."""

    permission_classes = [IsAuthenticated, IsOrganizationAdmin]

    def get_target(self, request, user_id):
        try:
            return Membership.objects.select_related("user").get(
                organization=request.organization, user_id=user_id
            )
        except Membership.DoesNotExist as exc:
            raise NotFound("Member not found.") from exc

    def patch(self, request, user_id):
        target = self.get_target(request, user_id)
        serializer = RoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_role = serializer.validated_data["role"]

        check_can_manage(request.membership, target, new_role)
        target.role = new_role
        target.save(update_fields=["role", "updated_at"])
        return Response(member_data(target))

    def delete(self, request, user_id):
        target = self.get_target(request, user_id)
        check_can_manage(request.membership, target)

        # Remove their per-document grants too, so re-adding them later gives no old access.
        DocumentAccess.objects.filter(
            user_id=target.user_id, document__organization=request.organization
        ).delete()
        target.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

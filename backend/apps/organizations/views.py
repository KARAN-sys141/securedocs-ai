from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Membership
from .permissions import IsOrganizationAdmin, IsOrganizationMember


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
    """Only owners and admins can list the members of their organization."""

    permission_classes = [IsAuthenticated, IsOrganizationAdmin]

    def get(self, request):
        members = Membership.objects.filter(organization=request.organization).select_related(
            "user"
        )
        data = [
            {
                "user_id": m.user_id,
                "username": m.user.username,
                "email": m.user.email,
                "role": m.role,
            }
            for m in members
        ]
        return Response(data)

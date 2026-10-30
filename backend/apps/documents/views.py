from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.organizations.models import Membership
from apps.organizations.permissions import IsOrganizationMember

from .access import can_manage_document, visible_documents
from .models import Document, DocumentAccess
from .serializers import DocumentSerializer, GrantSerializer, VisibilitySerializer


def get_visible_document(request, pk):
    """Returns the document, or 404 if it does not exist OR the user may not see it."""
    try:
        return visible_documents(request.membership).get(pk=pk)
    except Document.DoesNotExist as exc:
        raise NotFound("Document not found.") from exc


def require_manager(request, document):
    if not can_manage_document(request.membership, document):
        raise PermissionDenied("You cannot manage access to this document.")


class DocumentListView(APIView):
    permission_classes = [IsAuthenticated, IsOrganizationMember]

    def get(self, request):
        documents = visible_documents(request.membership).select_related("uploaded_by")
        return Response(DocumentSerializer(documents, many=True).data)


class DocumentDetailView(APIView):
    permission_classes = [IsAuthenticated, IsOrganizationMember]

    def get(self, request, pk):
        document = get_visible_document(request, pk)
        return Response(DocumentSerializer(document).data)

    def patch(self, request, pk):
        document = get_visible_document(request, pk)
        require_manager(request, document)
        serializer = VisibilitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document.visibility = serializer.validated_data["visibility"]
        document.save(update_fields=["visibility", "updated_at"])
        return Response(DocumentSerializer(document).data)


class DocumentAccessView(APIView):
    """List or add the people who may see a restricted document."""

    permission_classes = [IsAuthenticated, IsOrganizationMember]

    def get(self, request, pk):
        document = get_visible_document(request, pk)
        require_manager(request, document)
        grants = document.access_grants.select_related("user")
        return Response([{"user_id": g.user_id, "username": g.user.username} for g in grants])

    def post(self, request, pk):
        document = get_visible_document(request, pk)
        require_manager(request, document)
        serializer = GrantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_id = serializer.validated_data["user_id"]

        is_member = Membership.objects.filter(
            organization=request.organization, user_id=user_id
        ).exists()
        if not is_member:
            raise ValidationError("That user is not a member of this organization.")

        _, created = DocumentAccess.objects.get_or_create(
            document=document, user_id=user_id, defaults={"granted_by": request.user}
        )
        code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response({"user_id": user_id}, status=code)


class DocumentAccessDetailView(APIView):
    """Take away one person's access."""

    permission_classes = [IsAuthenticated, IsOrganizationMember]

    def delete(self, request, pk, user_id):
        document = get_visible_document(request, pk)
        require_manager(request, document)
        DocumentAccess.objects.filter(document=document, user_id=user_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

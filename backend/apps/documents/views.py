from django.conf import settings
from django.db.models import Sum
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.organizations.models import Membership
from apps.organizations.permissions import IsOrganizationMember

from .access import can_manage_document, visible_documents
from .models import Document, DocumentAccess
from .serializers import (
    DocumentSerializer,
    GrantSerializer,
    UploadSerializer,
    VisibilitySerializer,
)
from .validators import DuplicateUpload, PayloadTooLarge, sha256_of, validate_upload


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
    """GET: list the documents you may see. POST: upload a new document."""

    permission_classes = [IsAuthenticated, IsOrganizationMember]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        documents = visible_documents(request.membership).select_related("uploaded_by")
        return Response(DocumentSerializer(documents, many=True).data)

    def post(self, request):
        serializer = UploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        uploaded = data["file"]

        clean_name, content_type = validate_upload(uploaded)
        organization = request.organization

        # Storage quota for the whole organization
        used = (
            Document.objects.filter(organization=organization).aggregate(total=Sum("size_bytes"))[
                "total"
            ]
            or 0
        )
        if used + uploaded.size > settings.MAX_ORG_STORAGE_BYTES:
            raise PayloadTooLarge("Your organization's storage limit has been reached.")

        # Duplicate check: only against documents this user is allowed to see
        content_hash = sha256_of(uploaded)
        already_visible = visible_documents(request.membership).filter(content_hash=content_hash)
        if already_visible.exists():
            raise DuplicateUpload("You already have access to an identical file.")

        document = Document(
            organization=organization,
            uploaded_by=request.user,
            title=data.get("title") or clean_name,
            original_filename=clean_name,
            content_type=content_type,
            size_bytes=uploaded.size,
            content_hash=content_hash,
            visibility=data["visibility"],
            status=Document.Status.PENDING,
        )
        document.file.save(clean_name, uploaded, save=False)
        try:
            document.save()
        except Exception:
            document.file.delete(save=False)  # do not leave an orphan file behind
            raise

        return Response(DocumentSerializer(document).data, status=status.HTTP_201_CREATED)


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

    def delete(self, request, pk):
        document = get_visible_document(request, pk)
        require_manager(request, document)
        document.file.delete(save=False)  # remove the file from storage first
        document.delete()  # chunks and access grants are removed automatically
        return Response(status=status.HTTP_204_NO_CONTENT)


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

from django.db.models import Q

from apps.organizations.models import Membership

from .models import Chunk, Document

ADMIN_ROLES = (Membership.Role.OWNER, Membership.Role.ADMIN)


def visible_documents(membership):
    """Every document this membership may see. Always limited to its organization."""
    documents = Document.objects.filter(organization_id=membership.organization_id)
    if membership.role in ADMIN_ROLES:
        return documents
    return documents.filter(
        Q(visibility=Document.Visibility.ORGANIZATION)
        | Q(uploaded_by_id=membership.user_id)
        | Q(access_grants__user_id=membership.user_id)
    ).distinct()


def visible_chunks(membership):
    """Chunks from visible documents only. The AI search (Day 11) will use this."""
    return Chunk.objects.filter(
        organization_id=membership.organization_id,
        document__in=visible_documents(membership),
    )


def can_manage_document(membership, document):
    """Owners, admins and the uploader may change a document's access."""
    if document.organization_id != membership.organization_id:
        return False
    return membership.role in ADMIN_ROLES or document.uploaded_by_id == membership.user_id

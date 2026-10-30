import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from .models import Document
from .pipeline import PermanentProcessingError, TransientProcessingError, run_pipeline

logger = logging.getLogger(__name__)


def set_status(document_id, status, error=""):
    """Writes the new status straight to the database."""
    Document.objects.filter(pk=document_id).update(
        status=status,
        error_message=error,
        processing_started_at=None,
        updated_at=timezone.now(),
    )


def claim_document(document_id):
    """Moves a document to 'processing' in ONE atomic database update.

    Returns True only for the single worker that wins. A document that is
    already ready, failed, deleted, or being processed by someone else
    returns False. A 'processing' document older than the stale limit
    (its worker probably died) can be claimed again.
    """
    now = timezone.now()
    stale_before = now - timedelta(minutes=settings.PROCESSING_STALE_MINUTES)
    claimed = (
        Document.objects.filter(pk=document_id)
        .filter(
            Q(status=Document.Status.PENDING)
            | Q(status=Document.Status.PROCESSING, processing_started_at__lt=stale_before)
        )
        .update(
            status=Document.Status.PROCESSING,
            processing_started_at=now,
            error_message="",
            updated_at=now,
        )
    )
    return claimed == 1


@shared_task(bind=True, max_retries=3, acks_late=True)
def process_document(self, document_id):
    if not claim_document(document_id):
        logger.info("Document %s is not claimable; skipping.", document_id)
        return "skipped"

    document = Document.objects.filter(pk=document_id).first()
    if document is None:
        return "skipped"

    try:
        run_pipeline(document)
    except PermanentProcessingError as exc:
        set_status(document_id, Document.Status.FAILED, str(exc))
        return "failed"
    except TransientProcessingError as exc:
        if self.request.retries >= self.max_retries:
            message = "A temporary problem kept happening. Please try again later."
            set_status(document_id, Document.Status.FAILED, message)
            return "failed"
        # Release the claim so the retry can claim it again, then retry later
        set_status(document_id, Document.Status.PENDING)
        raise self.retry(exc=exc, countdown=20 * (2**self.request.retries)) from exc
    except Exception:
        logger.exception("Unexpected error while processing document %s", document_id)
        set_status(document_id, Document.Status.FAILED, "Unexpected error while processing.")
        return "failed"

    set_status(document_id, Document.Status.READY)
    return "ready"


def enqueue_processing(document_id):
    """Puts a document on the queue. Never crashes the caller if the queue is down."""
    try:
        process_document.delay(str(document_id))
        return True
    except Exception:
        logger.exception("Could not queue document %s", document_id)
        return False

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from apps.documents.models import Document
from apps.documents.tasks import enqueue_processing


class Command(BaseCommand):
    help = "Queue documents that are stuck in pending or in processing for too long."

    def handle(self, *args, **options):
        now = timezone.now()
        stale_before = now - timedelta(minutes=settings.PROCESSING_STALE_MINUTES)
        stuck = Document.objects.filter(
            Q(status=Document.Status.PENDING, created_at__lt=now - timedelta(minutes=2))
            | Q(status=Document.Status.PROCESSING, processing_started_at__lt=stale_before)
        )
        ids = list(stuck.values_list("pk", flat=True))
        for document_id in ids:
            enqueue_processing(document_id)
        self.stdout.write(f"Queued {len(ids)} document(s).")

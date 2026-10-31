from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.documents.models import Document


class Command(BaseCommand):
    help = "Print what the parser extracted from a document."

    def add_arguments(self, parser):
        parser.add_argument("document_id")

    def handle(self, *args, **options):
        try:
            document = Document.objects.get(pk=options["document_id"])
        except (Document.DoesNotExist, ValidationError) as exc:
            raise CommandError("Document not found.") from exc

        self.stdout.write(f"Title: {document.title}")
        self.stdout.write(f"Status: {document.status}  {document.error_message}")
        self.stdout.write(
            f"Pages in file: {document.page_count}  Characters: {document.char_count}"
        )
        for page in document.pages.all():
            self.stdout.write(f"\n--- Page {page.page_number} ({len(page.text)} characters) ---")
            self.stdout.write(page.text[:400])

from django.contrib import admin

from .models import Chunk, Document, DocumentPage


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "organization", "status", "visibility", "created_at")
    list_filter = ("status", "visibility")


@admin.register(Chunk)
class ChunkAdmin(admin.ModelAdmin):
    list_display = ("document", "chunk_index", "organization")
    exclude = ("embedding",)


@admin.register(DocumentPage)
class DocumentPageAdmin(admin.ModelAdmin):
    list_display = ("document", "page_number", "organization")

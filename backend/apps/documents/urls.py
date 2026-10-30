from django.urls import path

from .views import (
    DocumentAccessDetailView,
    DocumentAccessView,
    DocumentDetailView,
    DocumentListView,
    DocumentReprocessView,
)

urlpatterns = [
    path("documents/", DocumentListView.as_view(), name="document-list"),
    path("documents/<uuid:pk>/", DocumentDetailView.as_view(), name="document-detail"),
    path(
        "documents/<uuid:pk>/access/",
        DocumentAccessView.as_view(),
        name="document-access",
    ),
    path(
        "documents/<uuid:pk>/access/<int:user_id>/",
        DocumentAccessDetailView.as_view(),
        name="document-access-detail",
    ),
    path(
        "documents/<uuid:pk>/reprocess/",
        DocumentReprocessView.as_view(),
        name="document-reprocess",
    ),
]

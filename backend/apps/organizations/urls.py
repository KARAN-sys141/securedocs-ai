from django.urls import path

from .views import CurrentOrganizationView, MemberDetailView, MemberListView

urlpatterns = [
    path("org/", CurrentOrganizationView.as_view(), name="org-current"),
    path("org/members/", MemberListView.as_view(), name="org-members"),
    path("org/members/<int:user_id>/", MemberDetailView.as_view(), name="org-member"),
]

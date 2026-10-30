from django.urls import path

from .views import CurrentOrganizationView, MemberListView

urlpatterns = [
    path("org/", CurrentOrganizationView.as_view(), name="org-current"),
    path("org/members/", MemberListView.as_view(), name="org-members"),
]

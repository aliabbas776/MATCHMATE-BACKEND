"""
URL patterns for admin API endpoints.
All endpoints require admin authentication (is_staff=True).
"""

from django.urls import path

from .views_admin import (
    AdminDashboardStatsView,
    AdminProfileDetailView,
    AdminProfileRejectView,
    AdminProfileResetVerificationView,
    AdminProfilesPendingListView,
    AdminProfilesRejectedListView,
    AdminProfilesVerifiedListView,
    AdminProfileVerifyView,
)

app_name = 'admin'

urlpatterns = [
    # Dashboard
    path('dashboard/stats/', AdminDashboardStatsView.as_view(), name='dashboard-stats'),
    
    # Profile verification management
    path('profiles/pending/', AdminProfilesPendingListView.as_view(), name='profiles-pending'),
    path('profiles/verified/', AdminProfilesVerifiedListView.as_view(), name='profiles-verified'),
    path('profiles/rejected/', AdminProfilesRejectedListView.as_view(), name='profiles-rejected'),
    path('profiles/<int:profile_id>/', AdminProfileDetailView.as_view(), name='profile-detail'),
    path('profiles/<int:profile_id>/verify/', AdminProfileVerifyView.as_view(), name='profile-verify'),
    path('profiles/<int:profile_id>/reject/', AdminProfileRejectView.as_view(), name='profile-reject'),
    path('profiles/<int:profile_id>/reset-verification/', AdminProfileResetVerificationView.as_view(), name='profile-reset-verification'),
]

from django.urls import path

from .views import (
    CNICVerificationView,
    LoginView,
    MatchPreferenceView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    ProfileDescriptionView,
    ProfileListView,
    ProfilePhotoUploadView,
    ProfileSearchView,
    RegistrationView,
    UserAccountDeleteView,
    UserAccountView,
    UserProfileView,
)


urlpatterns = [
    path('register/', RegistrationView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('password-reset/request/', PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('account/', UserAccountView.as_view(), name='account'),
    path('account/delete/', UserAccountDeleteView.as_view(), name='account-delete'),
    path('profile/', UserProfileView.as_view(), name='profile'),
    path(
        'profile/description/',
        ProfileDescriptionView.as_view(),
        name='profile-description',
    ),
    path('profile/photo/', ProfilePhotoUploadView.as_view(), name='profile-photo'),
    path('cnic/verify/', CNICVerificationView.as_view(), name='cnic-verify'),
    path('preferences/', MatchPreferenceView.as_view(), name='match-preferences'),
    path('profiles/', ProfileListView.as_view(), name='profile-list'),
    path('profiles/search/', ProfileSearchView.as_view(), name='profile-search'),
]


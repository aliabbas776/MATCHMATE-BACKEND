from django.urls import path

from .views import (
    LoginView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    ProfileListView,
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
    path('profiles/', ProfileListView.as_view(), name='profile-list'),
]


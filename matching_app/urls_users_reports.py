"""
URL configuration for User and Report management ViewSets using routers.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views_users_reports import UserViewSet, ReportViewSet

# Create a router and register our viewsets with it
router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'reports', ReportViewSet, basename='report')

# The API URLs are now determined automatically by the router
urlpatterns = [
    path('', include(router.urls)),
]


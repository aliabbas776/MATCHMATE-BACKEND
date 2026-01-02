"""
Production-ready REST API ViewSets for User and Report management.

This module provides ViewSets using Django REST Framework best practices:
- ModelViewSets with proper permissions
- Pagination
- Clean error handling
- JWT authentication
"""
from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.pagination import PageNumberPagination

from django.utils import timezone
from .models import UserReport
from .permissions import IsAdminOrReadOwnProfile, ReportPermission
from .serializers import (
    UserCreateSerializer, 
    UserSerializer, 
    ReportSerializer,
    ReportReviewSerializer
)

User = get_user_model()


class StandardResultsSetPagination(PageNumberPagination):
    """Standard pagination class for list views."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for User management.
    
    Provides:
    - POST /api/users/ - Create a user (admin only)
    - GET /api/users/ - List users with pagination (admin only)
    - GET /api/users/{id}/ - Retrieve a user (admin can see any, users can see own)
    - DELETE /api/users/{id}/ - Delete a user (admin only)
    """
    queryset = User.objects.all()
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdminOrReadOwnProfile]
    pagination_class = StandardResultsSetPagination
    serializer_class = UserSerializer
    
    def get_serializer_class(self):
        """Use UserCreateSerializer for create, UserSerializer for other actions."""
        if self.action == 'create':
            return UserCreateSerializer
        return UserSerializer
    
    def get_queryset(self):
        """
        Filter queryset based on user permissions.
        - Admin users: see all users
        - Regular users: see only themselves (for list view, they'll see empty list)
        """
        queryset = User.objects.all().order_by('-date_joined')
        
        # Admin users can see all users
        if self.request.user.is_staff or self.request.user.is_superuser:
            # Optional: Add search/filtering for admin
            search = self.request.query_params.get('search', None)
            if search:
                queryset = queryset.filter(
                    Q(username__icontains=search) |
                    Q(email__icontains=search) |
                    Q(first_name__icontains=search) |
                    Q(last_name__icontains=search)
                )
            
            is_active = self.request.query_params.get('is_active', None)
            if is_active is not None:
                queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        else:
            # Regular users can only see themselves
            queryset = queryset.filter(id=self.request.user.id)
        
        return queryset
    
    def get_object(self):
        """
        Override to ensure users can only retrieve their own profile
        (unless admin).
        """
        obj = super().get_object()
        self.check_object_permissions(self.request, obj)
        return obj
    
    def create(self, request, *args, **kwargs):
        """Create a new user. Only admin users can create users."""
        if not (request.user.is_staff or request.user.is_superuser):
            return Response(
                {'detail': 'You do not have permission to perform this action.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            UserSerializer(serializer.instance).data,
            status=status.HTTP_201_CREATED,
            headers=headers
        )
    
    def destroy(self, request, *args, **kwargs):
        """Delete a user. Only admin users can delete users."""
        if not (request.user.is_staff or request.user.is_superuser):
            return Response(
                {'detail': 'You do not have permission to perform this action.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(
            {'detail': 'User deleted successfully.'},
            status=status.HTTP_204_NO_CONTENT
        )


class ReportViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Report management.
    
    Provides:
    - POST /api/reports/ - Create a report (authenticated users)
    - GET /api/reports/ - List reports (users see own, admins see all)
    - GET /api/reports/{id}/ - Retrieve a report (users see own, admins see all)
    - DELETE /api/reports/{id}/ - Delete a report (owner or admin only)
    """
    queryset = UserReport.objects.all()
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, ReportPermission]
    pagination_class = StandardResultsSetPagination
    serializer_class = ReportSerializer
    
    def get_queryset(self):
        """
        Filter queryset based on user permissions.
        - Admin users: see all reports
        - Regular users: see only their own reports
        """
        queryset = UserReport.objects.all().select_related(
            'reporter', 'reported_user', 'reviewed_by'
        ).order_by('-created_at')
        
        # Admin users can see all reports
        if self.request.user.is_staff or self.request.user.is_superuser:
            # Optional: Add filtering for admin
            status_filter = self.request.query_params.get('status', None)
            if status_filter:
                queryset = queryset.filter(status=status_filter)
            
            reporter_id = self.request.query_params.get('reporter', None)
            if reporter_id:
                queryset = queryset.filter(reporter_id=reporter_id)
            
            reported_user_id = self.request.query_params.get('reported_user', None)
            if reported_user_id:
                queryset = queryset.filter(reported_user_id=reported_user_id)
        else:
            # Regular users can only see their own reports
            queryset = queryset.filter(reporter=self.request.user)
        
        return queryset
    
    def get_object(self):
        """Override to check object-level permissions."""
        obj = super().get_object()
        self.check_object_permissions(self.request, obj)
        return obj
    
    def create(self, request, *args, **kwargs):
        """Create a new report. Only authenticated users can create reports."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
            headers=headers
        )
    
    def destroy(self, request, *args, **kwargs):
        """Delete a report. Only report owner or admin can delete."""
        instance = self.get_object()
        
        # Double-check permission (should already be checked by permission class)
        if not (request.user.is_staff or request.user.is_superuser or instance.reporter == request.user):
            return Response(
                {'detail': 'You do not have permission to perform this action.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        self.perform_destroy(instance)
        return Response(
            {'detail': 'Report deleted successfully.'},
            status=status.HTTP_204_NO_CONTENT
        )
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdminUser])
    def review(self, request, pk=None):
        """
        Admin endpoint to review a report (approve or decline).
        
        POST /api/manage/reports/{id}/review/
        Body: {"status": "reviewed"} or {"status": "dismissed"}
        """
        report = self.get_object()
        
        # Check if report is already reviewed
        if report.status != 'pending':
            return Response(
                {
                    'detail': f'Report has already been {report.status}. Cannot change status.',
                    'current_status': report.status
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = ReportReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        new_status = serializer.validated_data['status']
        
        # Update report status
        report.status = new_status
        report.reviewed_by = request.user
        report.reviewed_at = timezone.now()
        report.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'updated_at'])
        
        # Check if we need to re-enable any profiles (if dismissing reports)
        re_enabled_count = 0
        if new_status == 'dismissed':
            from django.db.models import Count
            from .models import UserProfile
            
            # Check if reported user's pending reports dropped below threshold
            pending_count = UserReport.objects.filter(
                reported_user=report.reported_user,
                status='pending'
            ).aggregate(
                distinct_count=Count('reporter', distinct=True)
            )['distinct_count']
            
            # If pending reports < 5, re-enable profile if it was disabled
            if pending_count < 5:
                try:
                    profile = UserProfile.objects.get(user=report.reported_user)
                    if profile.is_disabled:
                        profile.is_disabled = False
                        profile.disabled_reason = ''
                        profile.save(update_fields=['is_disabled', 'disabled_reason', 'updated_at'])
                        
                        # Re-activate user account
                        if not report.reported_user.is_active:
                            report.reported_user.is_active = True
                            report.reported_user.save(update_fields=['is_active'])
                        
                        re_enabled_count = 1
                except UserProfile.DoesNotExist:
                    pass
        
        # Return updated report
        response_serializer = ReportSerializer(report, context={'request': request})
        return Response(
            {
                'detail': f'Report marked as {new_status}.',
                'report': response_serializer.data,
                're_enabled_count': re_enabled_count
            },
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdminUser])
    def approve(self, request, pk=None):
        """
        Admin endpoint to approve a report (shortcut for review with status="reviewed").
        
        POST /api/manage/reports/{id}/approve/
        """
        # Set status to reviewed
        request.data['status'] = 'reviewed'
        return self.review(request, pk)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdminUser])
    def decline(self, request, pk=None):
        """
        Admin endpoint to decline/dismiss a report (shortcut for review with status="dismissed").
        
        POST /api/manage/reports/{id}/decline/
        """
        # Set status to dismissed
        request.data['status'] = 'dismissed'
        return self.review(request, pk)


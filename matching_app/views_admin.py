"""
Admin API views for managing user profiles, reports, and other administrative tasks.
Requires staff/admin authentication.
"""

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.pagination import PageNumberPagination

from .models import UserProfile
from .serializers import UserProfileListSerializer

User = get_user_model()


class AdminProfilePagination(PageNumberPagination):
    """Pagination for admin profile lists."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class AdminProfileVerifyView(APIView):
    """
    Admin endpoint to verify/approve a user profile.
    
    POST /api/admin/profiles/{profile_id}/verify/
    
    Sets admin_verification_status to 'verified' and records timestamp.
    This allows the profile to reach 100% completion.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def post(self, request, profile_id):
        try:
            profile = UserProfile.objects.select_related('user').get(id=profile_id)
        except UserProfile.DoesNotExist:
            return Response(
                {
                    'error': 'Profile not found',
                    'detail': f'Profile with ID {profile_id} does not exist.'
                },
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Update verification status
        old_status = profile.admin_verification_status
        profile.admin_verification_status = 'verified'
        profile.admin_verified_at = timezone.now()
        profile.save(update_fields=['admin_verification_status', 'admin_verified_at', 'updated_at'])
        
        return Response(
            {
                'success': True,
                'message': f'Profile for user {profile.user.username} has been verified.',
                'profile_id': profile.id,
                'user_id': profile.user.id,
                'username': profile.user.username,
                'previous_status': old_status,
                'new_status': 'verified',
                'verified_at': profile.admin_verified_at.isoformat() if profile.admin_verified_at else None,
                'verified_by': request.user.username,
            },
            status=status.HTTP_200_OK
        )


class AdminProfileRejectView(APIView):
    """
    Admin endpoint to reject a user profile verification.
    
    POST /api/admin/profiles/{profile_id}/reject/
    Body (optional): {
        "reason": "Reason for rejection"
    }
    
    Sets admin_verification_status to 'rejected'.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def post(self, request, profile_id):
        try:
            profile = UserProfile.objects.select_related('user').get(id=profile_id)
        except UserProfile.DoesNotExist:
            return Response(
                {
                    'error': 'Profile not found',
                    'detail': f'Profile with ID {profile_id} does not exist.'
                },
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get optional rejection reason
        reason = request.data.get('reason', '')
        
        # Update verification status
        old_status = profile.admin_verification_status
        profile.admin_verification_status = 'rejected'
        # Clear verified_at timestamp since it's rejected
        profile.admin_verified_at = None
        profile.save(update_fields=['admin_verification_status', 'admin_verified_at', 'updated_at'])
        
        return Response(
            {
                'success': True,
                'message': f'Profile for user {profile.user.username} has been rejected.',
                'profile_id': profile.id,
                'user_id': profile.user.id,
                'username': profile.user.username,
                'previous_status': old_status,
                'new_status': 'rejected',
                'reason': reason,
                'rejected_by': request.user.username,
            },
            status=status.HTTP_200_OK
        )


class AdminProfileResetVerificationView(APIView):
    """
    Admin endpoint to reset profile verification status back to pending.
    
    POST /api/admin/profiles/{profile_id}/reset-verification/
    
    Sets admin_verification_status back to 'pending'.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def post(self, request, profile_id):
        try:
            profile = UserProfile.objects.select_related('user').get(id=profile_id)
        except UserProfile.DoesNotExist:
            return Response(
                {
                    'error': 'Profile not found',
                    'detail': f'Profile with ID {profile_id} does not exist.'
                },
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Reset verification status
        old_status = profile.admin_verification_status
        profile.admin_verification_status = 'pending'
        profile.admin_verified_at = None
        profile.save(update_fields=['admin_verification_status', 'admin_verified_at', 'updated_at'])
        
        return Response(
            {
                'success': True,
                'message': f'Profile verification for user {profile.user.username} has been reset to pending.',
                'profile_id': profile.id,
                'user_id': profile.user.id,
                'username': profile.user.username,
                'previous_status': old_status,
                'new_status': 'pending',
                'reset_by': request.user.username,
            },
            status=status.HTTP_200_OK
        )


class AdminProfilesPendingListView(APIView):
    """
    Admin endpoint to list profiles pending verification.
    
    GET /api/admin/profiles/pending/
    
    Query params:
    - page: Page number (default: 1)
    - page_size: Results per page (default: 20, max: 100)
    - search: Search by username, email, candidate_name
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class = AdminProfilePagination
    
    def get(self, request):
        # Get profiles with pending verification
        queryset = UserProfile.objects.filter(
            admin_verification_status='pending'
        ).select_related('user').order_by('-created_at')
        
        # Search functionality
        search = request.query_params.get('search', '').strip()
        if search:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(user__username__icontains=search) |
                Q(user__email__icontains=search) |
                Q(candidate_name__icontains=search)
            )
        
        # Paginate
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)
        
        if page is not None:
            serializer = UserProfileListSerializer(page, many=True, context={'request': request})
            return paginator.get_paginated_response(serializer.data)
        
        # Fallback without pagination
        serializer = UserProfileListSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminProfilesVerifiedListView(APIView):
    """
    Admin endpoint to list verified profiles.
    
    GET /api/admin/profiles/verified/
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class = AdminProfilePagination
    
    def get(self, request):
        queryset = UserProfile.objects.filter(
            admin_verification_status='verified'
        ).select_related('user').order_by('-admin_verified_at')
        
        # Search functionality
        search = request.query_params.get('search', '').strip()
        if search:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(user__username__icontains=search) |
                Q(user__email__icontains=search) |
                Q(candidate_name__icontains=search)
            )
        
        # Paginate
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)
        
        if page is not None:
            serializer = UserProfileListSerializer(page, many=True, context={'request': request})
            return paginator.get_paginated_response(serializer.data)
        
        serializer = UserProfileListSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminProfilesRejectedListView(APIView):
    """
    Admin endpoint to list rejected profiles.
    
    GET /api/admin/profiles/rejected/
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class = AdminProfilePagination
    
    def get(self, request):
        queryset = UserProfile.objects.filter(
            admin_verification_status='rejected'
        ).select_related('user').order_by('-updated_at')
        
        # Search functionality
        search = request.query_params.get('search', '').strip()
        if search:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(user__username__icontains=search) |
                Q(user__email__icontains=search) |
                Q(candidate_name__icontains=search)
            )
        
        # Paginate
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)
        
        if page is not None:
            serializer = UserProfileListSerializer(page, many=True, context={'request': request})
            return paginator.get_paginated_response(serializer.data)
        
        serializer = UserProfileListSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminProfileDetailView(APIView):
    """
    Admin endpoint to get detailed profile information.
    
    GET /api/admin/profiles/{profile_id}/
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def get(self, request, profile_id):
        try:
            profile = UserProfile.objects.select_related('user').get(id=profile_id)
        except UserProfile.DoesNotExist:
            return Response(
                {
                    'error': 'Profile not found',
                    'detail': f'Profile with ID {profile_id} does not exist.'
                },
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = UserProfileListSerializer(profile, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminDashboardStatsView(APIView):
    """
    Admin endpoint to get dashboard statistics.
    
    GET /api/admin/dashboard/stats/
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def get(self, request):
        from django.db.models import Count
        
        # Profile verification stats
        profile_stats = UserProfile.objects.aggregate(
            total=Count('id'),
            pending=Count('id', filter=models.Q(admin_verification_status='pending')),
            verified=Count('id', filter=models.Q(admin_verification_status='verified')),
            rejected=Count('id', filter=models.Q(admin_verification_status='rejected')),
        )
        
        # User stats
        user_stats = User.objects.aggregate(
            total=Count('id'),
            active=Count('id', filter=models.Q(is_active=True)),
            inactive=Count('id', filter=models.Q(is_active=False)),
            staff=Count('id', filter=models.Q(is_staff=True)),
        )
        
        return Response(
            {
                'profiles': profile_stats,
                'users': user_stats,
            },
            status=status.HTTP_200_OK
        )

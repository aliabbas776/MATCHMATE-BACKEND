"""
Admin API views for managing user profiles, reports, and other administrative tasks.
Requires staff/admin authentication.
"""

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.pagination import PageNumberPagination

from .models import CNICVerification, UserProfile
from .permissions import IsStaffOrSuperuser
from .serializers import CNICVerificationSerializer, UserProfileListSerializer

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
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    
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
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    
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
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    
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
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
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
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
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
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
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


class AdminProfilesAllListView(APIView):
    """
    Admin endpoint to list ALL user profiles with filtering and search.
    
    GET /api/admin/profiles/all/
    
    Query params:
    - page: Page number (default: 1)
    - page_size: Results per page (default: 20, max: 100)
    - search: Search by username, email, candidate_name, phone_number, city
    - admin_verification_status: Filter by verification status (pending/verified/rejected)
    - gender: Filter by gender
    - country: Filter by country
    - city: Filter by city
    - is_public: Filter by public/private profiles (true/false)
    - is_disabled: Filter by disabled profiles (true/false)
    - cnic_verification_status: Filter by CNIC status (unverified/pending/verified/rejected)
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    pagination_class = AdminProfilePagination
    
    def get(self, request):
        from django.db.models import Q
        
        # Start with all profiles
        queryset = UserProfile.objects.select_related('user').order_by('-created_at')
        
        # Search functionality
        search = request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(user__username__icontains=search) |
                Q(user__email__icontains=search) |
                Q(candidate_name__icontains=search) |
                Q(phone_number__icontains=search) |
                Q(city__icontains=search)
            )
        
        # Filter by admin verification status
        admin_verification_status = request.query_params.get('admin_verification_status', '').strip().lower()
        if admin_verification_status in ['pending', 'verified', 'rejected']:
            queryset = queryset.filter(admin_verification_status=admin_verification_status)
        
        # Filter by gender
        gender = request.query_params.get('gender', '').strip()
        if gender:
            queryset = queryset.filter(gender__iexact=gender)
        
        # Filter by country
        country = request.query_params.get('country', '').strip()
        if country:
            queryset = queryset.filter(country__icontains=country)
        
        # Filter by city
        city = request.query_params.get('city', '').strip()
        if city:
            queryset = queryset.filter(city__icontains=city)
        
        # Filter by is_public
        is_public = request.query_params.get('is_public', '').strip().lower()
        if is_public == 'true':
            queryset = queryset.filter(is_public=True)
        elif is_public == 'false':
            queryset = queryset.filter(is_public=False)
        
        # Filter by is_disabled
        is_disabled = request.query_params.get('is_disabled', '').strip().lower()
        if is_disabled == 'true':
            queryset = queryset.filter(is_disabled=True)
        elif is_disabled == 'false':
            queryset = queryset.filter(is_disabled=False)
        
        # Filter by CNIC verification status
        cnic_status = request.query_params.get('cnic_verification_status', '').strip().lower()
        if cnic_status in ['unverified', 'pending', 'verified', 'rejected']:
            queryset = queryset.filter(cnic_verification_status=cnic_status)
        
        # Filter by marital status
        marital_status = request.query_params.get('marital_status', '').strip()
        if marital_status:
            queryset = queryset.filter(marital_status__iexact=marital_status)
        
        # Paginate
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)
        
        if page is not None:
            serializer = UserProfileListSerializer(page, many=True, context={'request': request})
            return paginator.get_paginated_response(serializer.data)
        
        # Fallback without pagination
        serializer = UserProfileListSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminProfileDetailView(APIView):
    """
    Admin endpoint to get detailed profile information.
    
    GET /api/admin/profiles/{profile_id}/
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    
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


class AdminCNICVerificationView(APIView):
    """
    Admin endpoint to get CNIC verification data for any user.
    
    GET /api/admin/cnic/{user_id}/
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    
    def get(self, request, user_id):
        # Check if user exists
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {
                    'error': 'User not found',
                    'detail': f'User with ID {user_id} does not exist.'
                },
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get CNIC verification for this user
        try:
            verification = CNICVerification.objects.get(user=user)
            serializer = CNICVerificationSerializer(verification, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except CNICVerification.DoesNotExist:
            return Response(
                {
                    'error': 'CNIC not found',
                    'detail': f'No CNIC verification found for user {user.username} (ID: {user_id}).',
                    'user_info': {
                        'id': user.id,
                        'username': user.username,
                        'email': user.email,
                    },
                    'status': 'not_uploaded'
                },
                status=status.HTTP_404_NOT_FOUND
            )


class AdminCNICListView(APIView):
    """
    Admin endpoint to list all CNIC verifications with filtering.
    
    GET /api/admin/cnic/all/
    
    Query params:
    - status: Filter by verification status (pending/verified/rejected)
    - tampering_detected: Filter by tampering (true/false)
    - search: Search by username, email, name, or CNIC number
    - page: Page number
    - page_size: Results per page
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    pagination_class = AdminProfilePagination
    
    def get(self, request):
        from django.db.models import Q
        
        # Get all CNIC verifications
        queryset = CNICVerification.objects.select_related('user').order_by('-updated_at')
        
        # Filter by status
        status_param = request.query_params.get('status', '').strip().lower()
        if status_param in ['pending', 'verified', 'rejected']:
            queryset = queryset.filter(status=status_param)
        
        # Filter by tampering detected
        tampering = request.query_params.get('tampering_detected', '').strip().lower()
        if tampering == 'true':
            queryset = queryset.filter(tampering_detected=True)
        elif tampering == 'false':
            queryset = queryset.filter(tampering_detected=False)
        
        # Search functionality
        search = request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(user__username__icontains=search) |
                Q(user__email__icontains=search) |
                Q(extracted_full_name__icontains=search) |
                Q(extracted_cnic__icontains=search)
            )
        
        # Paginate
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request)
        
        if page is not None:
            serializer = CNICVerificationSerializer(page, many=True, context={'request': request})
            return paginator.get_paginated_response(serializer.data)
        
        # Fallback without pagination
        serializer = CNICVerificationSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminDashboardStatsView(APIView):
    """
    Admin endpoint to get dashboard statistics.
    
    GET /api/admin/dashboard/stats/
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    
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
        
        # CNIC verification stats
        cnic_stats = CNICVerification.objects.aggregate(
            total=Count('id'),
            pending=Count('id', filter=models.Q(status='pending')),
            verified=Count('id', filter=models.Q(status='verified')),
            rejected=Count('id', filter=models.Q(status='rejected')),
            tampering_detected=Count('id', filter=models.Q(tampering_detected=True)),
        )
        
        return Response(
            {
                'profiles': profile_stats,
                'users': user_stats,
                'cnic_verifications': cnic_stats,
            },
            status=status.HTTP_200_OK
        )

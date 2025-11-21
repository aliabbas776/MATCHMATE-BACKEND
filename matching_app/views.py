from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken

from django.contrib.auth import get_user_model
from rest_framework.pagination import PageNumberPagination

from .models import UserProfile
from .serializers import (
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegistrationSerializer,
    UserAccountSerializer,
    UserProfileListSerializer,
    UserProfileSectionSerializer,
)

User = get_user_model()


class RegistrationView(APIView):
    """
    Public endpoint used by the mobile app to register new accounts.
    """

    authentication_classes = []
    permission_classes = []
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        serializer = RegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            data = {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'phone_number': user.profile.phone_number if hasattr(user, 'profile') else None,
                'profile_picture': request.build_absolute_uri(user.profile.profile_picture.url)
                if hasattr(user, 'profile') and user.profile.profile_picture
                else None,
            }
            return Response(data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    """
    Public endpoint used by the mobile app to authenticate users.
    Returns JWT access and refresh tokens upon successful login.
    """

    authentication_classes = []
    permission_classes = []
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            
            # Get user profile data
            profile_picture_url = None
            if hasattr(user, 'profile') and user.profile.profile_picture:
                profile_picture_url = request.build_absolute_uri(user.profile.profile_picture.url)
            
            data = {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'phone_number': user.profile.phone_number if hasattr(user, 'profile') else None,
                    'profile_picture': profile_picture_url,
                }
            }
            return Response(data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetRequestView(APIView):
    """
    Public endpoint to request an OTP for password reset.
    """

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {'detail': 'OTP has been sent to your email.'},
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetConfirmView(APIView):
    """
    Public endpoint to verify OTP and set a new password.
    """

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        reset_token = request.headers.get('X-Reset-Token')
        serializer = PasswordResetConfirmSerializer(
            data=request.data,
            context={'reset_token': reset_token},
        )
        if serializer.is_valid():
            result = serializer.save()
            return Response(result, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserProfileView(APIView):
    """
    Authenticated endpoint that handles the full multi-step profile in a single payload.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def _get_profile(self, user):
        profile, _ = UserProfile.objects.get_or_create(
            user=user,
            defaults={
                'phone_country_code': '+92',
                'phone_number': '',
            },
        )
        return profile

    def get(self, request):
        profile = self._get_profile(request.user)
        serializer = UserProfileSectionSerializer(profile, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request):
        profile = self._get_profile(request.user)
        serializer = UserProfileSectionSerializer(
            profile,
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        profile = self._get_profile(request.user)
        serializer = UserProfileSectionSerializer(
            profile,
            data=request.data,
            partial=True,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request):
        """Delete user profile."""
        try:
            profile = UserProfile.objects.get(user=request.user)
            profile.delete()
            return Response(
                {'detail': 'Profile deleted successfully.'},
                status=status.HTTP_200_OK,
            )
        except UserProfile.DoesNotExist:
            return Response(
                {'detail': 'Profile not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )


class UserAccountView(APIView):
    """
    Authenticated endpoint for updating user account details.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get(self, request):
        """Get user account details."""
        serializer = UserAccountSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        """Update user account details (partial update via POST)."""
        serializer = UserAccountSerializer(
            request.user,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        updated_user = serializer.save()
        # Return the updated data
        response_serializer = UserAccountSerializer(updated_user)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    def put(self, request):
        """Update user account details (full update)."""
        serializer = UserAccountSerializer(
            request.user,
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)
        updated_user = serializer.save()
        # Return the updated data
        response_serializer = UserAccountSerializer(updated_user)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        """Update user account details (partial update)."""
        serializer = UserAccountSerializer(
            request.user,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        updated_user = serializer.save()
        # Return the updated data
        response_serializer = UserAccountSerializer(updated_user)
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class UserAccountDeleteView(APIView):
    """
    Authenticated endpoint for deleting user account.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        """Delete user account and associated profile."""
        user = request.user
        # Delete profile if it exists
        try:
            profile = UserProfile.objects.get(user=user)
            profile.delete()
        except UserProfile.DoesNotExist:
            pass
        
        # Delete user account
        user.delete()
        return Response(
            {'detail': 'User account deleted successfully.'},
            status=status.HTTP_200_OK,
        )


class StandardResultsSetPagination(PageNumberPagination):
    """Pagination class for profile listing."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class ProfileListView(APIView):
    """
    Authenticated endpoint for listing user profiles (for matching).
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get(self, request):
        """List all user profiles (excluding current user)."""
        profiles = UserProfile.objects.exclude(user=request.user).select_related('user')
        
        # Apply pagination
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(profiles, request)
        
        if page is not None:
            serializer = UserProfileListSerializer(
                page,
                many=True,
                context={'request': request},
            )
            return paginator.get_paginated_response(serializer.data)
        
        serializer = UserProfileListSerializer(
            profiles,
            many=True,
            context={'request': request},
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

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
from django.core.files.base import ContentFile

from .openai_helpers import generate_profile_description, validate_profile_photo
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


def get_or_create_user_profile(user):
    profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={
            'phone_country_code': '+92',
            'phone_number': '',
        },
    )
    return profile


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
    Public endpoint used by the mobile app to authenticate users and report profile status.
    """

    authentication_classes = []
    permission_classes = []
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'success': False, 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = serializer.validated_data['user']
        refresh = RefreshToken.for_user(user)
        has_profile = UserProfile.objects.filter(user=user).exists()

        return Response(
            {
                'success': True,
                'token': str(refresh.access_token),
                'hasProfile': has_profile,
            },
            status=status.HTTP_200_OK,
        )


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

    def get(self, request):
        profile = get_or_create_user_profile(request.user)
        serializer = UserProfileSectionSerializer(profile, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request):
        profile = get_or_create_user_profile(request.user)
        serializer = UserProfileSectionSerializer(
            profile,
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        profile = get_or_create_user_profile(request.user)
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


class ProfileDescriptionView(APIView):
    """
    Authenticated endpoint that uses OpenAI to create a short dating app
    description once the profile is complete.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile = get_or_create_user_profile(request.user)
        description = generate_profile_description(profile)
        profile.generated_description = description
        profile.save(update_fields=['generated_description'])
        return Response(
            {'generated_description': description},
            status=status.HTTP_200_OK,
        )


class ProfilePhotoUploadView(APIView):
    """
    Validate and store a single human profile photo using OpenAI Vision.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        upload = request.FILES.get('file') or request.FILES.get('photo')
        if not upload:
            return Response(
                {'allowed': False, 'reason': 'No image file was provided.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        image_bytes = upload.read()
        allowed, reason = validate_profile_photo(image_bytes, upload.name)
        if not allowed:
            return Response(
                {'allowed': False, 'reason': reason},
                status=status.HTTP_400_BAD_REQUEST,
            )

        profile = get_or_create_user_profile(request.user)
        profile.profile_picture.save(
            upload.name,
            ContentFile(image_bytes),
            save=True,
        )

        image_url = request.build_absolute_uri(profile.profile_picture.url)
        return Response(
            {'allowed': True, 'reason': 'Photo accepted.', 'profile_picture': image_url},
            status=status.HTTP_200_OK,
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
        """List profiles that match the logged-in user's preferences."""
        viewer_profile = get_or_create_user_profile(request.user)

        required_fields = ['gender', 'city', 'caste', 'religion']
        missing_fields = [field for field in required_fields if not getattr(viewer_profile, field)]
        if missing_fields:
            return Response(
                {
                    'detail': 'Complete your profile before browsing matches.',
                    'missing_fields': missing_fields,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        opposite_gender_map = {
            'male': 'female',
            'female': 'male',
        }
        target_gender = opposite_gender_map.get(viewer_profile.gender.lower())
        if not target_gender:
            return Response(
                {'detail': 'Unsupported gender. Please update your profile.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        profiles = (
            UserProfile.objects.exclude(user=request.user)
            .filter(
                gender=target_gender,
                city=viewer_profile.city,
                caste=viewer_profile.caste,
                religion=viewer_profile.religion,
            )
            .select_related('user')
        )

        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(profiles, request)

        serializer = UserProfileListSerializer(
            page if page is not None else profiles,
            many=True,
            context={'request': request},
        )

        if page is not None:
            return paginator.get_paginated_response(serializer.data)
        return Response(serializer.data, status=status.HTTP_200_OK)

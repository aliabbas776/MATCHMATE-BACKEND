from datetime import date
from typing import Optional

from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.pagination import PageNumberPagination

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.utils import timezone

from .models import CNICVerification, MatchPreference, UserProfile

from .ocr_utils import analyze_cnic_images
from .openai_helpers import generate_profile_description, validate_profile_photo
from .serializers import (
    CNICVerificationSerializer,
    LoginSerializer,
    MatchPreferenceSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegistrationSerializer,
    UserAccountSerializer,
    UserProfileListSerializer,
    UserProfileSectionSerializer,
)

User = get_user_model()


def _normalize_cnic_value(raw: Optional[str]) -> Optional[str]:
    """
    Bring CNIC numbers into #####-#######-# format for reliable comparisons.
    """
    if not raw:
        return None
    digits = ''.join(ch for ch in raw if ch.isdigit())
    if len(digits) != 13:
        return raw.strip() or None
    return f'{digits[:5]}-{digits[5:12]}-{digits[-1]}'


def get_or_create_user_profile(user):
    profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={
            'phone_country_code': '+92',
            'phone_number': '',
        },
    )
    return profile


def get_or_create_match_preference(user):
    preference, _ = MatchPreference.objects.get_or_create(user=user)
    return preference


def _subtract_years(reference_date: date, years: int) -> date:
    try:
        return reference_date.replace(year=reference_date.year - years)
    except ValueError:
        # Handle February 29th by falling back to February 28th
        return reference_date.replace(month=2, day=28, year=reference_date.year - years)


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
        profile = getattr(user, 'profile', None)
        has_profile = bool(profile and profile.is_completed)

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


class CNICVerificationView(APIView):
    """
    Accept CNIC images, run OCR, and auto-approve/reject.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        front_file = request.FILES.get('front_image')
        back_file = request.FILES.get('back_image')
        if not front_file or not back_file:
            return Response(
                {'detail': 'Both front_image and back_image files are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        front_bytes = front_file.read()
        back_bytes = back_file.read()

        result = analyze_cnic_images(front_bytes, back_bytes)
        issues: list[str] = []

        extracted_cnic_normalized = _normalize_cnic_value(result.cnic_number)

        if not extracted_cnic_normalized:
            issues.append('CNIC number could not be detected or has invalid format.')

        if not result.full_name:
            issues.append('Full name could not be extracted.')

        if not result.date_of_birth:
            issues.append('Date of birth could not be extracted.')

        if result.tampering_detected:
            issues.append('Image quality too low or potential tampering detected.')

        profile = get_or_create_user_profile(request.user)

        extracted_dob = result.date_of_birth.date() if result.date_of_birth else None

        if result.full_name and profile.candidate_name:
            profile_name_normalized = ' '.join(profile.candidate_name.lower().split())
            cnic_name_normalized = ' '.join(result.full_name.lower().split())
            if (
                cnic_name_normalized not in profile_name_normalized
                and profile_name_normalized not in cnic_name_normalized
            ):
                issues.append('CNIC name does not match profile name.')

        if extracted_dob and profile.date_of_birth:
            if extracted_dob != profile.date_of_birth:
                issues.append('CNIC date of birth does not match profile date of birth.')

        if result.gender and profile.gender:
            if result.gender.lower() != profile.gender.lower():
                issues.append('CNIC gender does not match profile gender.')

        profile_cnic_normalized = _normalize_cnic_value(profile.cnic_number)
        if extracted_cnic_normalized and profile_cnic_normalized:
            if extracted_cnic_normalized != profile_cnic_normalized:
                issues.append('CNIC number does not match the number on file.')

        duplicate = (
            extracted_cnic_normalized
            and CNICVerification.objects.filter(
                extracted_cnic=extracted_cnic_normalized,
                status=CNICVerification.Status.VERIFIED,
            )
            .exclude(user=request.user)
            .exists()
        )
        if duplicate:
            issues.append('This CNIC number is already verified for another account.')

        verification, _ = CNICVerification.objects.get_or_create(user=request.user)
        verification.front_image.save(front_file.name, ContentFile(front_bytes), save=False)
        verification.back_image.save(back_file.name, ContentFile(back_bytes), save=False)
        verification.extracted_full_name = result.full_name or ''
        verification.extracted_cnic = extracted_cnic_normalized or ''
        verification.extracted_gender = result.gender or ''
        verification.extracted_dob = extracted_dob
        verification.blur_score = result.blur_score
        verification.tampering_detected = result.tampering_detected

        profile_updates = ['cnic_verification_status', 'cnic_verified_at']

        if issues:
            verification.status = CNICVerification.Status.REJECTED
            verification.rejection_reason = '; '.join(issues)
            profile.cnic_verification_status = 'rejected'
            profile.cnic_verified_at = None
        else:
            verification.status = CNICVerification.Status.VERIFIED
            verification.rejection_reason = ''
            if extracted_cnic_normalized:
                profile.cnic_number = extracted_cnic_normalized
                if 'cnic_number' not in profile_updates:
                    profile_updates.append('cnic_number')
            profile.cnic_verification_status = 'verified'
            profile.cnic_verified_at = timezone.now()

        profile.save(update_fields=profile_updates)
        verification.save()

        serializer = CNICVerificationSerializer(verification)
        return Response(serializer.data, status=status.HTTP_200_OK)


class MatchPreferenceView(APIView):
    """
    Manage the logged-in user's saved search preferences.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        preference = get_or_create_match_preference(request.user)
        serializer = MatchPreferenceSerializer(preference)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request):
        preference = get_or_create_match_preference(request.user)
        serializer = MatchPreferenceSerializer(preference, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        preference = get_or_create_match_preference(request.user)
        serializer = MatchPreferenceSerializer(preference, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


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

        required_fields = ['gender', 'city', 'caste', 'religion', 'country']
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
                country=viewer_profile.country,
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


class ProfileSearchView(APIView):
    """
    Search for profiles using either query params or saved preferences.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def _value_from_params(self, request, preference, param_name, preference_attr):
        if param_name in request.query_params:
            value = request.query_params.get(param_name)
            return value or None
        return getattr(preference, preference_attr)

    def _boolean_from_params(self, request, preference, param_name, preference_attr):
        if param_name in request.query_params:
            raw = request.query_params.get(param_name)
            if raw is None or raw == '':
                return None
            return raw.lower() in {'1', 'true', 'yes'}
        return getattr(preference, preference_attr)

    def _age_bounds(self, request, preference):
        min_age = self._value_from_params(request, preference, 'min_age', 'min_age')
        max_age = self._value_from_params(request, preference, 'max_age', 'max_age')
        exact_age = request.query_params.get('age')
        if exact_age and exact_age.isdigit():
            min_age = max_age = int(exact_age)
        min_age = int(min_age) if min_age not in (None, '') else None
        max_age = int(max_age) if max_age not in (None, '') else None
        return min_age, max_age

    def get(self, request):
        preference = get_or_create_match_preference(request.user)
        queryset = UserProfile.objects.exclude(user=request.user).select_related('user')

        field_map = {
            'status': 'marital_status',
            'religion': 'religion',
            'caste': 'caste',
            'country': 'country',
            'city': 'city',
            'employment_status': 'employment_status',
            'profession': 'profession',
        }

        for param, model_field in field_map.items():
            value = self._value_from_params(request, preference, param, param)
            if value:
                queryset = queryset.filter(**{model_field: value})

        disability_pref = self._boolean_from_params(request, preference, 'disability', 'prefers_disability')
        if disability_pref is True:
            queryset = queryset.filter(has_disability=True)
        elif disability_pref is False:
            queryset = queryset.filter(has_disability=False)

        min_age, max_age = self._age_bounds(request, preference)
        today = timezone.now().date()
        if min_age is not None or max_age is not None:
            queryset = queryset.filter(date_of_birth__isnull=False)
        if max_age is not None:
            min_birth_date = _subtract_years(today, max_age)
            queryset = queryset.filter(date_of_birth__gte=min_birth_date)
        if min_age is not None:
            max_birth_date = _subtract_years(today, min_age)
            queryset = queryset.filter(date_of_birth__lte=max_birth_date)

        queryset = queryset.order_by('-updated_at')

        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = UserProfileListSerializer(
            page if page is not None else queryset,
            many=True,
            context={'request': request},
        )
        if page is not None:
            return paginator.get_paginated_response(serializer.data)
        return Response(serializer.data, status=status.HTTP_200_OK)

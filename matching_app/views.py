from datetime import date, timedelta
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
from django.db.models import F
from django.db import transaction

from .models import CNICVerification, MatchPreference, SubscriptionPlan, UserProfile, UserReport, UserSubscription

from .ocr_utils import analyze_cnic_images
from .openai_helpers import generate_profile_description, validate_profile_photo
from .serializers import (
    CNICVerificationSerializer,
    LoginSerializer,
    MatchPreferenceSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegistrationSerializer,
    SubscriptionPlanSerializer,
    SubscriptionUpgradeSerializer,
    UserAccountSerializer,
    UserProfileListSerializer,
    UserProfileSectionSerializer,
    UserReportSerializer,
    UserSubscriptionSerializer,
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


def get_or_create_user_subscription(user):
    """Get or create user subscription, defaulting to FREE plan if doesn't exist."""
    try:
        subscription = UserSubscription.objects.get(user=user)
        return subscription
    except UserSubscription.DoesNotExist:
        # Get FREE plan
        free_plan = SubscriptionPlan.objects.get(tier=SubscriptionPlan.PlanTier.FREE)
        subscription = UserSubscription.objects.create(
            user=user,
            plan=free_plan,
            status=UserSubscription.SubscriptionStatus.ACTIVE,
        )
        return subscription


def check_and_reenable_profile_if_needed(reported_user):
    """
    Check if a user's profile should be re-enabled after reports are dismissed.
    Re-enables profile if pending reports drop below 5.
    Returns True if profile was re-enabled, False otherwise.
    """
    from django.db.models import Count
    from django.db import transaction
    
    # Count remaining pending reports
    pending_count = UserReport.objects.filter(
        reported_user=reported_user,
        status='pending'
    ).aggregate(
        distinct_count=Count('reporter', distinct=True)
    )['distinct_count']
    
    # If pending reports drop below 5, re-enable the profile
    if pending_count < 5:
        try:
            profile = UserProfile.objects.get(user=reported_user)
            if profile.is_disabled:
                with transaction.atomic():
                    profile.is_disabled = False
                    profile.disabled_reason = ''
                    # Keep disabled_at for audit trail
                    profile.save(update_fields=['is_disabled', 'disabled_reason', 'updated_at'])
                    
                    # Re-activate the user account
                    reported_user.is_active = True
                    reported_user.save(update_fields=['is_active'])
                return True
        except UserProfile.DoesNotExist:
            pass
    
    return False


def check_and_disable_profile_if_needed(reported_user):
    """
    Check if a user has been reported by 5 distinct users and disable their profile if so.
    Returns True if profile was disabled, False otherwise.
    """
    from django.db.models import Count
    from django.db import transaction
    
    # Count distinct reporters (users who have reported this user) - more reliable method
    distinct_reporters_count = UserReport.objects.filter(
        reported_user=reported_user,
        status='pending'
    ).aggregate(
        distinct_count=Count('reporter', distinct=True)
    )['distinct_count']
    
    if distinct_reporters_count >= 5:
        try:
            profile = UserProfile.objects.get(user=reported_user)
            if not profile.is_disabled:
                # Use transaction to ensure atomicity
                with transaction.atomic():
                    profile.is_disabled = True
                    profile.disabled_at = timezone.now()
                    profile.disabled_reason = f'Profile disabled automatically after being reported by {distinct_reporters_count} different users.'
                    profile.save(update_fields=['is_disabled', 'disabled_at', 'disabled_reason', 'updated_at'])
                    
                    # Also deactivate the user account
                    reported_user.is_active = False
                    reported_user.save(update_fields=['is_active'])
                return True
        except UserProfile.DoesNotExist:
            # If profile doesn't exist, create it and disable it
            with transaction.atomic():
                profile = UserProfile.objects.create(
                    user=reported_user,
                    is_disabled=True,
                    disabled_at=timezone.now(),
                    disabled_reason=f'Profile disabled automatically after being reported by {distinct_reporters_count} different users.',
                )
                reported_user.is_active = False
                reported_user.save(update_fields=['is_active'])
            return True
        except Exception as e:
            # Log the error but don't fail silently
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error disabling profile for user {reported_user.id}: {str(e)}")
            return False
    
    return False


def _get_matching_profiles(user, preference):
    """
    Get profiles that match the user's preferences with opposite gender.
    """
    viewer_profile = get_or_create_user_profile(user)
    
    # Determine opposite gender
    opposite_gender_map = {
        'male': 'female',
        'female': 'male',
    }
    target_gender = opposite_gender_map.get(viewer_profile.gender.lower() if viewer_profile.gender else None)
    
    if not target_gender:
        return UserProfile.objects.none()
    
    queryset = UserProfile.objects.exclude(user=user).filter(gender=target_gender).select_related('user')
    
    # Apply preference filters
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
        value = getattr(preference, param, None)
        if value:
            queryset = queryset.filter(**{model_field: value})
    
    # Disability filter
    if preference.prefers_disability is True:
        queryset = queryset.filter(has_disability=True)
    elif preference.prefers_disability is False:
        queryset = queryset.filter(has_disability=False)
    
    # Age filter
    today = timezone.now().date()
    if preference.min_age is not None or preference.max_age is not None:
        queryset = queryset.filter(date_of_birth__isnull=False)
    if preference.max_age is not None:
        min_birth_date = _subtract_years(today, preference.max_age)
        queryset = queryset.filter(date_of_birth__gte=min_birth_date)
    if preference.min_age is not None:
        max_birth_date = _subtract_years(today, preference.min_age)
        queryset = queryset.filter(date_of_birth__lte=max_birth_date)
    
    return queryset.order_by('-updated_at')


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
        
        # Check and update profile status based on current report count (in case admin changed reports)
        from django.db.models import Count
        pending_count = UserReport.objects.filter(
            reported_user=user,
            status='pending'
        ).aggregate(
            distinct_count=Count('reporter', distinct=True)
        )['distinct_count']
        
        # If user has 5+ pending reports, disable the profile
        if pending_count >= 5:
            check_and_disable_profile_if_needed(user)
        
        # Check if user's profile is disabled
        try:
            profile = UserProfile.objects.get(user=user)
            if profile.is_disabled:
                return Response(
                    {
                        'success': False,
                        'error': 'Account Disabled',
                        'detail': 'Your profile has been disabled due to multiple reports. Please contact admin for assistance.',
                        'disabled_at': profile.disabled_at.isoformat() if profile.disabled_at else None,
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
        except UserProfile.DoesNotExist:
            pass
        
        # Also check if user account is active
        if not user.is_active:
            return Response(
                {
                    'success': False,
                    'error': 'Account Disabled',
                    'detail': 'Your account has been disabled due to multiple reports. Please contact admin for assistance.',
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        
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

    def _check_profile_disabled(self, user):
        """Check if user's profile is disabled and raise error if so."""
        try:
            profile = UserProfile.objects.get(user=user)
            if profile.is_disabled:
                return Response(
                    {
                        'error': 'Profile Disabled',
                        'detail': 'Your profile has been disabled due to multiple reports. Please contact admin for assistance.',
                        'disabled_at': profile.disabled_at.isoformat() if profile.disabled_at else None,
                        'disabled_reason': profile.disabled_reason,
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
        except UserProfile.DoesNotExist:
            pass
        return None

    def get(self, request):
        # Check if profile is disabled
        disabled_response = self._check_profile_disabled(request.user)
        if disabled_response:
            return disabled_response
        
        profile = get_or_create_user_profile(request.user)
        serializer = UserProfileSectionSerializer(profile, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request):
        # Check if profile is disabled
        disabled_response = self._check_profile_disabled(request.user)
        if disabled_response:
            return disabled_response
        
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
        # Check if profile is disabled
        disabled_response = self._check_profile_disabled(request.user)
        if disabled_response:
            return disabled_response
        
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


class ProfileCompletionView(APIView):
    """
    Authenticated endpoint that returns profile completion percentage.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get profile completion percentage."""
        profile = get_or_create_user_profile(request.user)
        completion_data = profile.get_completion_percentage()
        return Response(completion_data, status=status.HTTP_200_OK)


class DashboardProfileCompletionView(APIView):
    """
    Authenticated endpoint for dashboard that returns profile completion percentage.
    Returns a simple, dashboard-friendly response with completion percentage.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get profile completion percentage for dashboard."""
        profile = get_or_create_user_profile(request.user)
        completion_data = profile.get_completion_percentage()
        
        # Return a clean, dashboard-friendly response
        return Response(
            {
                'completion_percentage': completion_data['completion_percentage'],
                'is_completed': completion_data['is_completed'],
                'message': f"Your profile is {completion_data['completion_percentage']}% complete",
            },
            status=status.HTTP_200_OK,
        )


class ProfileDescriptionView(APIView):
    """
    Authenticated endpoint that uses OpenAI to create a short dating app
    description once the profile is complete.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Check if profile is disabled
        try:
            profile = UserProfile.objects.get(user=request.user)
            if profile.is_disabled:
                return Response(
                    {
                        'error': 'Profile Disabled',
                        'detail': 'Your profile has been disabled due to multiple reports. Please contact admin for assistance.',
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
        except UserProfile.DoesNotExist:
            pass
        
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
        # Check if profile is disabled
        try:
            profile_check = UserProfile.objects.get(user=request.user)
            if profile_check.is_disabled:
                return Response(
                    {
                        'allowed': False,
                        'reason': 'Your profile has been disabled due to multiple reports. Please contact admin for assistance.',
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
        except UserProfile.DoesNotExist:
            pass
        
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
        # Check if profile is disabled
        try:
            profile_check = UserProfile.objects.get(user=request.user)
            if profile_check.is_disabled:
                return Response(
                    {
                        'detail': 'Your profile has been disabled due to multiple reports. Please contact admin for assistance.',
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
        except UserProfile.DoesNotExist:
            pass
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
    Returns matching profiles with opposite gender after saving preferences.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        preference = get_or_create_match_preference(request.user)
        serializer = MatchPreferenceSerializer(preference)
        
        # Get matching profiles
        matching_profiles = _get_matching_profiles(request.user, preference)
        profile_serializer = UserProfileListSerializer(
            matching_profiles,
            many=True,
            context={'request': request},
        )
        
        return Response({
            'preferences': serializer.data,
            'matching_profiles': profile_serializer.data,
            'total_matches': matching_profiles.count(),
        }, status=status.HTTP_200_OK)

    def put(self, request):
        preference = get_or_create_match_preference(request.user)
        serializer = MatchPreferenceSerializer(preference, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        # Refresh preference from DB to get updated values
        preference.refresh_from_db()
        
        # Get matching profiles
        matching_profiles = _get_matching_profiles(request.user, preference)
        profile_serializer = UserProfileListSerializer(
            matching_profiles,
            many=True,
            context={'request': request},
        )
        
        return Response({
            'preferences': serializer.data,
            'matching_profiles': profile_serializer.data,
            'total_matches': matching_profiles.count(),
        }, status=status.HTTP_200_OK)

    def patch(self, request):
        preference = get_or_create_match_preference(request.user)
        serializer = MatchPreferenceSerializer(preference, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        # Refresh preference from DB to get updated values
        preference.refresh_from_db()
        
        # Get matching profiles
        matching_profiles = _get_matching_profiles(request.user, preference)
        profile_serializer = UserProfileListSerializer(
            matching_profiles,
            many=True,
            context={'request': request},
        )
        
        return Response({
            'preferences': serializer.data,
            'matching_profiles': profile_serializer.data,
            'total_matches': matching_profiles.count(),
        }, status=status.HTTP_200_OK)


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


class UserProfileDetailView(APIView):
    """
    Authenticated endpoint to view a specific user's profile by user_id (URL parameter) or query parameter.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id=None):
        """Get a specific user's profile by user_id."""
        # Get user_id from URL parameter or query parameter
        target_user_id = user_id or request.query_params.get('user_id')
        profile_id = request.query_params.get('profile_id')
        
        if not target_user_id and not profile_id:
            return Response(
                {'error': 'Either user_id (in URL or query) or profile_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            if target_user_id:
                # Get profile by user_id
                profile = UserProfile.objects.select_related('user').get(user_id=target_user_id)
            else:
                # Get profile by profile_id
                profile = UserProfile.objects.select_related('user').get(id=profile_id)
        except UserProfile.DoesNotExist:
            return Response(
                {'error': 'Profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Don't allow users to view their own profile through this endpoint (use /api/profile/ instead)
        if profile.user == request.user:
            return Response(
                {'error': 'Use /api/profile/ endpoint to view your own profile'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if profile is disabled
        if profile.is_disabled:
            return Response(
                {
                    'error': 'Profile Disabled',
                    'detail': 'This profile has been disabled.',
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        
        # Check if user account is active
        if not profile.user.is_active:
            return Response(
                {
                    'error': 'Account Inactive',
                    'detail': 'This account is inactive.',
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        
        # Check subscription limits for profile views
        with transaction.atomic():
            # Lock and reload subscription with plan relationship to get latest values
            subscription = UserSubscription.objects.select_related('plan').select_for_update().get(
                user=request.user
            )
            
            # Check if subscription is active
            if not subscription.is_active:
                return Response(
                    {
                        'error': 'Subscription Expired',
                        'detail': 'Your subscription has expired. Please renew to continue using this feature.',
                        'upgrade_required': True,
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            
            # Check profile view limit (must check BEFORE viewing profile)
            max_profile_views = subscription.plan.max_profile_views
            profile_views_used = subscription.profile_views_used
            
            if max_profile_views != -1:  # Not unlimited
                # CRITICAL: Block if user has reached or exceeded the limit
                if profile_views_used >= max_profile_views:
                    return Response(
                        {
                            'error': 'Profile View Limit Exceeded',
                            'detail': f'You have reached your monthly limit of {max_profile_views} profile views. You have used {profile_views_used} profile views.',
                            'limit': max_profile_views,
                            'used': profile_views_used,
                            'upgrade_required': True,
                            'message': 'Please upgrade your subscription plan to view more profiles.',
                        },
                        status=status.HTTP_403_FORBIDDEN,
                    )
            
            # Only increment counter if limit check passes (user is within limit)
            UserSubscription.objects.filter(user=request.user).update(
                profile_views_used=F('profile_views_used') + 1
            )
        
        serializer = UserProfileListSerializer(profile, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class UserReportView(APIView):
    """
    Authenticated endpoint for users to report other users.
    Automatically disables profile if user receives 5 reports.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get report statistics for debugging (admin only or self-check)."""
        from django.db.models import Count
        
        reported_user_id = request.query_params.get('reported_user_id')
        if not reported_user_id:
            return Response(
                {'error': 'reported_user_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            reported_user = User.objects.get(id=reported_user_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get report statistics
        report_info = UserReport.objects.filter(
            reported_user=reported_user,
            status='pending'
        ).aggregate(
            total_reports=Count('id'),
            distinct_reporters=Count('reporter', distinct=True)
        )
        
        # Get list of distinct reporters
        distinct_reporters = UserReport.objects.filter(
            reported_user=reported_user,
            status='pending'
        ).values('reporter__id', 'reporter__username', 'reporter__email').distinct()
        
        try:
            profile = UserProfile.objects.get(user=reported_user)
            profile_status = {
                'is_disabled': profile.is_disabled,
                'disabled_at': profile.disabled_at.isoformat() if profile.disabled_at else None,
                'disabled_reason': profile.disabled_reason,
            }
        except UserProfile.DoesNotExist:
            profile_status = None
        
        # Check if profile should be disabled or re-enabled (manual trigger)
        should_disable = report_info['distinct_reporters'] >= 5
        
        # If should be disabled but isn't, disable it
        if should_disable and profile_status and not profile_status['is_disabled']:
            # Manually trigger disable check
            profile_disabled = check_and_disable_profile_if_needed(reported_user)
            if profile_disabled:
                # Refresh profile status
                profile = UserProfile.objects.get(user=reported_user)
                reported_user.refresh_from_db()
                profile_status = {
                    'is_disabled': profile.is_disabled,
                    'disabled_at': profile.disabled_at.isoformat() if profile.disabled_at else None,
                    'disabled_reason': profile.disabled_reason,
                }
        
        # If shouldn't be disabled but is, re-enable it
        if not should_disable and profile_status and profile_status['is_disabled']:
            # Manually trigger re-enable check
            profile_reenabled = check_and_reenable_profile_if_needed(reported_user)
            if profile_reenabled:
                # Refresh profile status
                profile = UserProfile.objects.get(user=reported_user)
                reported_user.refresh_from_db()
                profile_status = {
                    'is_disabled': profile.is_disabled,
                    'disabled_at': profile.disabled_at.isoformat() if profile.disabled_at else None,
                    'disabled_reason': profile.disabled_reason,
                }
        
        return Response({
            'reported_user_id': reported_user.id,
            'reported_user_username': reported_user.username,
            'total_pending_reports': report_info['total_reports'],
            'distinct_reporters_count': report_info['distinct_reporters'],
            'distinct_reporters': list(distinct_reporters),
            'user_is_active': reported_user.is_active,
            'profile_status': profile_status,
            'should_be_disabled': should_disable,
        }, status=status.HTTP_200_OK)

    def post(self, request):
        """Create a report against another user."""
        serializer = UserReportSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        report = serializer.save()
        
        # Check if reported user should be disabled
        profile_disabled = check_and_disable_profile_if_needed(report.reported_user)
        
        response_data = {
            'id': report.id,
            'reported_user_id': report.reported_user_id,
            'reason': report.reason,
            'description': report.description,
            'status': report.status,
            'message': 'Report submitted successfully.',
            'created_at': report.created_at.isoformat(),
        }
        
        if profile_disabled:
            response_data['warning'] = 'The reported user\'s profile has been automatically disabled due to multiple reports.'
        
        # Also return the current report count for debugging
        from django.db.models import Count
        report_count_info = UserReport.objects.filter(
            reported_user=report.reported_user,
            status='pending'
        ).aggregate(
            total_reports=Count('id'),
            distinct_reporters=Count('reporter', distinct=True)
        )
        response_data['report_count'] = {
            'total_pending_reports': report_count_info['total_reports'],
            'distinct_reporters': report_count_info['distinct_reporters'],
        }
        
        return Response(response_data, status=status.HTTP_201_CREATED)


class SubscriptionPlanListView(APIView):
    """
    Authenticated endpoint to list all available subscription plans.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get all active subscription plans."""
        plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price')
        serializer = SubscriptionPlanSerializer(plans, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UserSubscriptionView(APIView):
    """
    Authenticated endpoint to view and manage user's subscription.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get current user's subscription."""
        subscription = get_or_create_user_subscription(request.user)
        serializer = UserSubscriptionSerializer(subscription)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        """Subscribe or upgrade to a subscription plan."""
        serializer = SubscriptionUpgradeSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        
        plan_id = serializer.validated_data['plan_id']
        auto_renew = serializer.validated_data.get('auto_renew', False)
        
        plan = SubscriptionPlan.objects.get(id=plan_id)
        user = request.user
        
        # Get or create user subscription
        try:
            subscription = UserSubscription.objects.get(user=user)
            # Update existing subscription
            subscription.plan = plan
            subscription.status = UserSubscription.SubscriptionStatus.ACTIVE
            subscription.auto_renew = auto_renew
            subscription.cancelled_at = None
            subscription.cancellation_reason = ''
            
            # Set expiration date based on plan duration
            if plan.duration_days > 0:
                subscription.expires_at = timezone.now() + timedelta(days=plan.duration_days)
            else:
                subscription.expires_at = None  # Lifetime subscription
            
            subscription.save()
        except UserSubscription.DoesNotExist:
            # Set expiration date based on plan duration
            expires_at = None
            if plan.duration_days > 0:
                expires_at = timezone.now() + timedelta(days=plan.duration_days)
            
            subscription = UserSubscription.objects.create(
                user=user,
                plan=plan,
                status=UserSubscription.SubscriptionStatus.ACTIVE,
                auto_renew=auto_renew,
                expires_at=expires_at,
            )
        
        # Reset usage counters when upgrading
        subscription.reset_usage()
        
        response_serializer = UserSubscriptionSerializer(subscription)
        return Response(
            {
                'message': f'Successfully subscribed to {plan.name}',
                'subscription': response_serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class SubscriptionCancelView(APIView):
    """
    Authenticated endpoint to cancel user's subscription.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Cancel current user's subscription."""
        cancellation_reason = request.data.get('reason', '')
        
        try:
            subscription = UserSubscription.objects.get(user=request.user)
        except UserSubscription.DoesNotExist:
            return Response(
                {'error': 'No active subscription found'},
                status=status.HTTP_404_NOT_FOUND,
            )
        
        # Downgrade to FREE plan instead of cancelling
        free_plan = SubscriptionPlan.objects.get(tier=SubscriptionPlan.PlanTier.FREE)
        subscription.plan = free_plan
        subscription.status = UserSubscription.SubscriptionStatus.CANCELLED
        subscription.cancelled_at = timezone.now()
        subscription.cancellation_reason = cancellation_reason
        subscription.auto_renew = False
        subscription.expires_at = None  # Free plan doesn't expire
        subscription.save()
        
        # Reset usage counters
        subscription.reset_usage()
        
        serializer = UserSubscriptionSerializer(subscription)
        return Response(
            {
                'message': 'Subscription cancelled. You have been downgraded to Free plan.',
                'subscription': serializer.data,
            },
            status=status.HTTP_200_OK,
        )

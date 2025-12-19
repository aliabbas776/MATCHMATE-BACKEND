import json
import secrets
from collections import OrderedDict
from collections.abc import Mapping
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core import signing
from django.core.mail import send_mail
from django.db.models import Q
from django.http import QueryDict
from django.utils import timezone
from rest_framework import serializers

from . import models
from .models import (
    CNICVerification,
    MatchPreference,
    Message,
    PasswordResetOTP,
    SubscriptionPlan,
    UserConnection,
    UserProfile,
    UserProfileImage,
    UserReport,
    UserSubscription,
)
from .photo_visibility import get_photo_visibility_helper, resolve_profile_picture_url


User = get_user_model()


class RegistrationSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(required=True)
    last_name = serializers.CharField(required=True)
    email = serializers.EmailField(required=True)
    phone_number = serializers.CharField(required=True, write_only=True)
    profile_picture = serializers.ImageField(required=False, allow_null=True, write_only=True)
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        validators=[validate_password],
    )
    confirm_password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
    )

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'first_name',
            'last_name',
            'email',
            'phone_number',
            'profile_picture',
            'password',
            'confirm_password',
        ]

    def validate(self, attrs):
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError('Passwords do not match.')

        email = attrs['email']
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError('An account with this email already exists.')

        username = attrs['username']
        if User.objects.filter(username__iexact=username).exists():
            raise serializers.ValidationError('Username is already taken.')

        return attrs

    def create(self, validated_data):
        validated_data.pop('confirm_password')
        phone_number = validated_data.pop('phone_number')
        profile_picture = validated_data.pop('profile_picture', None)
        password = validated_data.pop('password')

        user = User.objects.create_user(password=password, **validated_data)
        UserProfile.objects.create(
            user=user,
            phone_number=phone_number,
            profile_picture=profile_picture,
        )
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'},
    )

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if email and password:
            # Try to get user by email (case-insensitive)
            # Use filter().first() to handle cases where multiple users exist with same email
            user = User.objects.filter(email__iexact=email).first()
            if not user:
                raise serializers.ValidationError('Invalid email or password.')

            # Check if user is active
            if not user.is_active:
                raise serializers.ValidationError('User account is disabled.')

            # Check password directly (more reliable than authenticate)
            if not user.check_password(password):
                raise serializers.ValidationError('Invalid email or password.')

            attrs['user'] = user
            return attrs
        else:
            missing = []
            if not email:
                missing.append('email')
            if not password:
                missing.append('password')
            raise serializers.ValidationError(f'Must include {", ".join(missing)}.')


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        try:
            user = User.objects.get(email__iexact=value)
        except User.DoesNotExist:
            raise serializers.ValidationError('No account found with this email.')

        if not user.is_active:
            raise serializers.ValidationError('User account is disabled.')

        self.user = user
        return value

    def _generate_unique_code(self):
        while True:
            code = f"{secrets.randbelow(10**4):04d}"
            if not PasswordResetOTP.objects.filter(code=code, is_used=False).exists():
                return code

    def save(self, **kwargs):
        user = self.user

        # invalidate previous unused OTPs
        PasswordResetOTP.objects.filter(user=user, is_used=False).update(is_used=True)

        code = self._generate_unique_code()
        expires_at = timezone.now() + timedelta(minutes=10)
        PasswordResetOTP.objects.create(user=user, code=code, expires_at=expires_at)

        subject = 'Matchmate Password Reset OTP'
        message = (
            f'Your password reset OTP is {code}. '
            'It expires in 10 minutes. If you did not request this, please ignore this email.'
        )
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])

        return {'email': user.email}


class PasswordResetConfirmSerializer(serializers.Serializer):
    STAGE_VERIFY = 'verify'
    STAGE_RESET = 'reset'
    RESET_TOKEN_MAX_AGE = 600  # seconds

    email = serializers.EmailField(required=False)
    otp = serializers.CharField(max_length=4, required=False)
    stage = serializers.ChoiceField(
        choices=[(STAGE_VERIFY, 'Verify OTP'), (STAGE_RESET, 'Reset Password')],
        required=False,
    )
    new_password = serializers.CharField(
        write_only=True,
        required=False,
        style={'input_type': 'password'},
        validators=[validate_password],
    )
    confirm_password = serializers.CharField(
        write_only=True,
        required=False,
        style={'input_type': 'password'},
    )

    def validate(self, attrs):
        reset_token = self.context.get('reset_token')
        stage = attrs.get('stage')
        if not stage:
            stage = self.STAGE_RESET if reset_token else self.STAGE_VERIFY
        attrs['stage'] = stage

        new_password = attrs.get('new_password')
        confirm_password = attrs.get('confirm_password')

        if stage == self.STAGE_VERIFY:
            email = attrs.get('email')
            otp = attrs.get('otp')
            if not email or not otp:
                raise serializers.ValidationError('Email and OTP are required for verification.')
            try:
                user = User.objects.get(email__iexact=email)
            except User.DoesNotExist:
                raise serializers.ValidationError('Invalid email or OTP.')
            otp_record = self._fetch_otp_record(user=user, code=otp)
            attrs['user'] = user
            attrs['otp_record'] = otp_record
        else:
            if not reset_token:
                reset_token = attrs.get('reset_token')
            if not new_password or not confirm_password:
                raise serializers.ValidationError('New password and confirmation are required.')
            if new_password != confirm_password:
                raise serializers.ValidationError('Passwords do not match.')
            otp_record = self._fetch_otp_from_token(reset_token)
            attrs['user'] = otp_record.user
            attrs['otp_record'] = otp_record
            attrs['new_password'] = new_password
        return attrs

    def _fetch_otp_record(self, user, code):
        try:
            otp_record = PasswordResetOTP.objects.get(
                user=user,
                code=code,
                is_used=False,
            )
        except PasswordResetOTP.DoesNotExist:
            raise serializers.ValidationError('Invalid or expired OTP.')

        if otp_record.is_expired():
            otp_record.is_used = True
            otp_record.save(update_fields=['is_used'])
            raise serializers.ValidationError('Invalid or expired OTP.')
        return otp_record

    def _fetch_otp_from_token(self, token):
        if not token:
            raise serializers.ValidationError('Reset token is required.')
        signer = signing.TimestampSigner()
        try:
            otp_id = signer.unsign(token, max_age=self.RESET_TOKEN_MAX_AGE)
        except signing.BadSignature:
            raise serializers.ValidationError('Invalid or expired reset token.')
        try:
            otp_record = PasswordResetOTP.objects.get(id=otp_id, is_used=False)
        except PasswordResetOTP.DoesNotExist:
            raise serializers.ValidationError('Invalid or expired reset token.')
        if otp_record.is_expired():
            otp_record.is_used = True
            otp_record.save(update_fields=['is_used'])
            raise serializers.ValidationError('Invalid or expired reset token.')
        return otp_record

    def save(self, **kwargs):
        user = self.validated_data['user']
        otp_record = self.validated_data['otp_record']
        stage = self.validated_data['stage']

        if stage == self.STAGE_VERIFY:
            token = signing.TimestampSigner().sign(str(otp_record.id))
            return {
                'detail': 'OTP verified successfully.',
                'reset_token': token,
                'token_expires_in_seconds': self.RESET_TOKEN_MAX_AGE,
            }

        new_password = self.validated_data['new_password']
        user.set_password(new_password)
        user.save(update_fields=['password'])

        otp_record.is_used = True
        otp_record.save(update_fields=['is_used'])
        PasswordResetOTP.objects.filter(user=user).exclude(id=otp_record.id).update(is_used=True)
        return {'detail': 'Password has been reset successfully.'}


class UserProfileSectionSerializer(serializers.ModelSerializer):
    """
    Serializer wrapping the whole multi-step profile into a single payload/response.
    """

    section_field_map = OrderedDict(
        [
            (
                'candidate_information',
                [
                    'candidate_name',
                    'email',
                    'hidden_name',
                    'date_of_birth',
                    'country',
                    'city',
                    'religion',
                    'sect',
                    'caste',
                    'height_cm',
                    'weight_kg',
                    'phone_country_code',
                    'phone_number',
                    'has_disability',
                ],
            ),
            (
                'profile_details',
                [
                    'profile_for',
                    'gender',
                    'marital_status',
                ],
            ),
            (
                'family_details',
                [
                    'father_status',
                    'father_employment_status',
                    'mother_status',
                    'mother_employment_status',
                ],
            ),
            (
                'siblings_details',
                [
                    'total_brothers',
                    'total_sisters',
                ],
            ),
            (
                'education_employment',
                [
                    'education_level',
                    'employment_status',
                    'profession',
                ],
            ),
            (
                'media',
                [
                    'profile_picture',
                    'blur_photo',
                    'is_public',
                ],
            ),
            (
                'images',
                [
                    'images',
                ],
            ),
        ]
    )
    profile_picture = serializers.ImageField(required=False, allow_null=True)
    has_disability = serializers.BooleanField(required=False)
    generated_description = serializers.CharField(read_only=True)
    email = serializers.EmailField(required=False, write_only=False)
    images = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = [
            'candidate_name',
            'email',
            'hidden_name',
            'date_of_birth',
            'country',
            'city',
            'religion',
            'sect',
            'caste',
            'height_cm',
            'weight_kg',
            'phone_country_code',
            'phone_number',
            'profile_for',
            'gender',
            'marital_status',
            'father_status',
            'father_employment_status',
            'mother_status',
            'mother_employment_status',
            'total_brothers',
            'total_sisters',
            'education_level',
            'employment_status',
            'profession',
            'profile_picture',
            'blur_photo',
            'is_public',
            'has_disability',
            'generated_description',
            'cnic_number',
            'cnic_verification_status',
            'cnic_verified_at',
            'images',
        ]
        read_only_fields = ['generated_description', 'cnic_verification_status', 'cnic_verified_at', 'images']

    def _as_plain_mapping(self, data):
        if isinstance(data, QueryDict):
            return {key: data.get(key) for key in data.keys()}
        if isinstance(data, Mapping):
            return dict(data)
        return data

    def _maybe_parse_json(self, value):
        if isinstance(value, str):
            trimmed = value.strip()
            if trimmed.startswith('{') and trimmed.endswith('}'):
                try:
                    return json.loads(trimmed)
                except json.JSONDecodeError:
                    pass
        return value

    def _flatten_sections(self, data):
        base = self._as_plain_mapping(data)
        if not isinstance(base, Mapping):
            return base

        dotted = {}
        for key in list(base.keys()):
            if '.' not in key:
                continue
            section, field = key.split('.', 1)
            if section in self.section_field_map and field in self.section_field_map[section]:
                dotted.setdefault(section, {})[field] = base.pop(key)

        for section, values in dotted.items():
            current = base.get(section)
            if isinstance(current, Mapping):
                merged = dict(current)
            else:
                current = self._maybe_parse_json(current)
                merged = dict(current) if isinstance(current, Mapping) else {}
            merged.update(values)
            base[section] = merged

        flattened = {}
        sections_present = False
        for section, fields in self.section_field_map.items():
            if section not in base:
                continue
            sections_present = True
            payload = self._maybe_parse_json(base[section])
            if not isinstance(payload, Mapping):
                raise serializers.ValidationError({section: 'Expected an object.'})
            for field in fields:
                if field in payload:
                    flattened[field] = payload[field]

        if not sections_present:
            return base

        for key, value in base.items():
            if key in self.section_field_map:
                continue
            flattened[key] = value
        return flattened

    def to_internal_value(self, data):
        flattened = self._flatten_sections(data)
        return super().to_internal_value(flattened)

    def get_images(self, instance):
        """Get all images for the profile as an array."""
        request = self.context.get('request')
        images = instance.images.all()
        image_list = []
        for img in images:
            if request:
                image_url = request.build_absolute_uri(img.image.url)
            else:
                image_url = img.image.url if img.image else None
            image_list.append({
                'id': img.id,
                'url': image_url,
                'order': img.order,
                'created_at': img.created_at.isoformat() if img.created_at else None,
            })
        return image_list

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        # Add email from user model
        if hasattr(instance, 'user') and instance.user:
            rep['email'] = instance.user.email
        request = self.context.get('request')
        helper = get_photo_visibility_helper(self.context)
        rep['profile_picture'] = resolve_profile_picture_url(instance, request, helper)
        
        # Get images array
        images_data = rep.pop('images', [])

        sectioned = OrderedDict()
        for section, fields in self.section_field_map.items():
            sectioned[section] = {field: rep.pop(field, None) for field in fields}
        
        # Add images to the images section
        sectioned['images'] = images_data

        generated_description = rep.pop('generated_description', None)
        cnic_number = rep.pop('cnic_number', None)
        cnic_status = rep.pop('cnic_verification_status', None)
        cnic_verified_at = rep.pop('cnic_verified_at', None)

        sectioned['meta'] = {
            'profile_id': instance.id,
            'user_id': instance.user_id,
            'created_at': instance.created_at.isoformat(),
            'updated_at': instance.updated_at.isoformat(),
        }
        if generated_description:
            sectioned['ai_generated_description'] = {
                'description': generated_description,
            }
        if any([cnic_number, cnic_status, cnic_verified_at]):
            verified_at = (
                cnic_verified_at.isoformat()
                if hasattr(cnic_verified_at, 'isoformat')
                else cnic_verified_at
            )
            sectioned['cnic_verification'] = {
                'number': cnic_number,
                'status': cnic_status,
                'verified_at': verified_at,
            }
        
        # Add profile completion percentage
        completion_data = instance.get_completion_percentage()
        sectioned['profile_completion'] = {
            'completion_percentage': completion_data['completion_percentage'],
            'is_completed': completion_data['is_completed'],
            'completed_fields': completion_data['completed_fields'],
            'total_fields': completion_data['total_fields'],
            'sections': completion_data['sections'],
        }
        
        return sectioned

    def save(self, **kwargs):
        # Handle email update if provided
        email = self.validated_data.pop('email', None)
        instance = super().save(**kwargs)
        
        # Update user email if provided
        if email is not None and hasattr(instance, 'user'):
            # Validate email uniqueness (excluding current user)
            User = get_user_model()
            if User.objects.filter(email__iexact=email).exclude(id=instance.user.id).exists():
                raise serializers.ValidationError({'email': 'A user with this email already exists.'})
            instance.user.email = email
            instance.user.save(update_fields=['email'])
        
        return instance


class UserAccountSerializer(serializers.ModelSerializer):
    """Serializer for updating user account details."""

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']
        read_only_fields = ['id']

    def validate_email(self, value):
        user = self.instance
        if User.objects.filter(email__iexact=value).exclude(id=user.id).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return value

    def validate_username(self, value):
        user = self.instance
        if User.objects.filter(username=value).exclude(id=user.id).exists():
            raise serializers.ValidationError('A user with this username already exists.')
        return value


class UserProfileListSerializer(serializers.ModelSerializer):
    """Serializer for listing profiles (public view for matching)."""
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)

    class Meta:
        model = UserProfile
        fields = [
            'id',
            'user_id',
            'username',
            'email',
            'first_name',
            'last_name',
            'candidate_name',
            'date_of_birth',
            'country',
            'city',
            'religion',
            'sect',
            'caste',
            'height_cm',
            'weight_kg',
            'profile_for',
            'gender',
            'marital_status',
            'education_level',
            'employment_status',
            'profession',
            'has_disability',
            'profile_picture',
            'is_public',
            'generated_description',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        request = self.context.get('request')
        helper = get_photo_visibility_helper(self.context)
        rep['profile_picture'] = resolve_profile_picture_url(instance, request, helper)
        return rep


class MatchPreferenceSerializer(serializers.ModelSerializer):
    """Serializer used to persist a user's search preferences."""

    class Meta:
        model = MatchPreference
        fields = [
            'status',
            'religion',
            'caste',
            'country',
            'city',
            'employment_status',
            'profession',
            'prefers_disability',
            'min_age',
            'max_age',
            'updated_at',
        ]
        read_only_fields = ['updated_at']

    def validate(self, attrs):
        min_age = attrs.get('min_age', getattr(self.instance, 'min_age', None))
        max_age = attrs.get('max_age', getattr(self.instance, 'max_age', None))
        if min_age is not None and min_age < 18:
            raise serializers.ValidationError({'min_age': 'Minimum age cannot be less than 18.'})
        if max_age is not None and max_age < 18:
            raise serializers.ValidationError({'max_age': 'Maximum age cannot be less than 18.'})
        if min_age is not None and max_age is not None and min_age > max_age:
            raise serializers.ValidationError({'min_age': 'Minimum age cannot exceed maximum age.'})
        return attrs


class CNICVerificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = CNICVerification
        fields = [
            'status',
            'extracted_full_name',
            'extracted_cnic',
            'extracted_dob',
            'extracted_gender',
            'rejection_reason',
            'tampering_detected',
            'blur_score',
            'updated_at',
        ]
        read_only_fields = fields


class ConnectionUserProfileSerializer(serializers.ModelSerializer):
    """Complete profile info for connection responses."""

    profile_picture = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = [
            'id',
            'candidate_name',
            'date_of_birth',
            'gender',
            'marital_status',
            'profile_for',
            'country',
            'city',
            'religion',
            'sect',
            'caste',
            'height_cm',
            'weight_kg',
            'education_level',
            'employment_status',
            'profession',
            'father_status',
            'mother_status',
            'total_brothers',
            'total_sisters',
            'has_disability',
            'profile_picture',
            'generated_description',
            'is_public',
            'blur_photo',
        ]

    def get_profile_picture(self, instance):
        request = self.context.get('request')
        helper = get_photo_visibility_helper(self.context)
        return resolve_profile_picture_url(instance, request, helper)


class ConnectionUserSummarySerializer(serializers.ModelSerializer):
    profile = ConnectionUserProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'profile']


class UserConnectionSerializer(serializers.ModelSerializer):
    connection_id = serializers.IntegerField(source='id', read_only=True)
    friend = serializers.SerializerMethodField()
    direction = serializers.SerializerMethodField()

    class Meta:
        model = UserConnection
        fields = ['id', 'connection_id', 'status', 'created_at', 'updated_at', 'friend', 'direction']

    def _resolve_friend(self, obj):
        request = self.context.get('request')
        request_user = getattr(request, 'user', None)
        if request_user and obj.from_user_id == request_user.id:
            return obj.to_user
        if request_user and obj.to_user_id == request_user.id:
            return obj.from_user
        return obj.to_user

    def get_friend(self, obj):
        friend = self._resolve_friend(obj)
        serializer = ConnectionUserSummarySerializer(friend)
        return serializer.data

    def get_direction(self, obj):
        request = self.context.get('request')
        request_user = getattr(request, 'user', None)
        if request_user and obj.from_user_id == request_user.id:
            return 'sent'
        if request_user and obj.to_user_id == request_user.id:
            return 'received'
        return 'unknown'


class ConnectionRequestSerializer(serializers.Serializer):
    to_user_id = serializers.PrimaryKeyRelatedField(
        source='to_user',
        queryset=User.objects.filter(is_active=True),
    )

    def validate(self, attrs):
        request_user = self.context['request'].user
        to_user = attrs['to_user']

        if request_user == to_user:
            raise serializers.ValidationError({'to_user_id': 'You cannot connect with yourself.'})

        existing_qs = UserConnection.objects.filter(
            Q(from_user=request_user, to_user=to_user) | Q(from_user=to_user, to_user=request_user)
        )

        active = existing_qs.filter(
            status__in=[UserConnection.Status.PENDING, UserConnection.Status.APPROVED]
        ).first()
        if active:
            message = (
                'You are already connected with this user.'
                if active.status == UserConnection.Status.APPROVED
                else 'A pending request already exists between these users.'
            )
            raise serializers.ValidationError({'to_user_id': message})

        attrs['recycled_connection'] = existing_qs.filter(
            status=UserConnection.Status.REJECTED
        ).order_by('-updated_at').first()
        return attrs

    def create(self, validated_data):
        request_user = self.context['request'].user
        to_user = validated_data['to_user']
        recycled = validated_data.pop('recycled_connection', None)
        if recycled:
            recycled.from_user = request_user
            recycled.to_user = to_user
            recycled.status = UserConnection.Status.PENDING
            recycled.save(update_fields=['from_user', 'to_user', 'status', 'updated_at'])
            return recycled
        return UserConnection.objects.create(from_user=request_user, to_user=to_user)


class ConnectionAcceptSerializer(serializers.Serializer):
    connection_id = serializers.IntegerField()

    def validate(self, attrs):
        request_user = self.context['request'].user
        connection_id = attrs['connection_id']
        try:
            connection = UserConnection.objects.select_related('from_user', 'to_user').get(
                id=connection_id,
                status=UserConnection.Status.PENDING,
                to_user=request_user,
            )
        except UserConnection.DoesNotExist:
            raise serializers.ValidationError(
                {'connection_id': 'Pending request not found or already processed.'}
            )
        attrs['connection'] = connection
        return attrs

    def save(self, **kwargs):
        connection = self.validated_data['connection']
        connection.status = UserConnection.Status.APPROVED
        connection.save(update_fields=['status', 'updated_at'])
        return connection


class ConnectionRejectSerializer(serializers.Serializer):
    connection_id = serializers.IntegerField()

    def validate(self, attrs):
        request_user = self.context['request'].user
        connection_id = attrs['connection_id']
        try:
            connection = UserConnection.objects.select_related('from_user', 'to_user').get(
                id=connection_id,
                status=UserConnection.Status.PENDING,
                to_user=request_user,
            )
        except UserConnection.DoesNotExist:
            raise serializers.ValidationError(
                {'connection_id': 'Pending request not found or already processed.'}
            )
        attrs['connection'] = connection
        return attrs

    def save(self, **kwargs):
        connection = self.validated_data['connection']
        connection.status = UserConnection.Status.REJECTED
        connection.save(update_fields=['status', 'updated_at'])
        return connection


class ConnectionCancelSerializer(serializers.Serializer):
    connection_id = serializers.IntegerField()

    def validate(self, attrs):
        request_user = self.context['request'].user
        connection_id = attrs['connection_id']
        try:
            connection = UserConnection.objects.get(
                id=connection_id,
                status=UserConnection.Status.PENDING,
                from_user=request_user,
            )
        except UserConnection.DoesNotExist:
            raise serializers.ValidationError(
                {'connection_id': 'Pending request not found or already processed.'}
            )
        attrs['connection'] = connection
        return attrs

    def save(self, **kwargs):
        connection = self.validated_data['connection']
        connection_id = connection.id
        connection.delete()
        return connection_id


class ConnectionRemoveSerializer(serializers.Serializer):
    connection_id = serializers.IntegerField()

    def validate(self, attrs):
        request_user = self.context['request'].user
        connection_id = attrs['connection_id']
        try:
            connection = UserConnection.objects.select_related('from_user', 'to_user').get(
                id=connection_id,
                status=UserConnection.Status.APPROVED,
            )
        except UserConnection.DoesNotExist:
            raise serializers.ValidationError(
                {'connection_id': 'Connection not found or already removed.'}
            )

        if connection.from_user_id != request_user.id and connection.to_user_id != request_user.id:
            raise serializers.ValidationError(
                {'connection_id': 'You do not have permission to modify this connection.'}
            )

        attrs['connection'] = connection
        return attrs

    def save(self, **kwargs):
        connection = self.validated_data['connection']
        connection_id = connection.id
        connection.delete()
        return connection_id


class MessageUserSerializer(serializers.ModelSerializer):
    """Serializer for user information in messages."""
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name']


class MessageSerializer(serializers.ModelSerializer):
    """Serializer for individual messages."""
    sender = MessageUserSerializer(read_only=True)
    receiver = MessageUserSerializer(read_only=True)

    class Meta:
        model = Message
        fields = ['id', 'sender', 'receiver', 'content', 'is_read', 'created_at']
        read_only_fields = ['id', 'sender', 'receiver', 'is_read', 'created_at']


class MessageCreateSerializer(serializers.Serializer):
    """Serializer for creating a new message."""
    receiver_id = serializers.IntegerField()
    content = serializers.CharField(required=True, max_length=5000)

    def validate_receiver_id(self, value):
        """Validate that the receiver exists and is active."""
        try:
            receiver = User.objects.get(id=value)
        except User.DoesNotExist:
            # Check if this might be a UserProfile ID instead
            try:
                profile = UserProfile.objects.get(id=value)
                user_id = profile.user_id
                raise serializers.ValidationError(
                    f'ID {value} is a UserProfile ID. Please use the User ID instead. '
                    f'For UserProfile ID {value}, the User ID is {user_id}.'
                )
            except UserProfile.DoesNotExist:
                pass
            
            raise serializers.ValidationError(f'User with ID {value} does not exist.')
        
        if not receiver.is_active:
            raise serializers.ValidationError(f'User with ID {value} is inactive.')
        
        # Store receiver in context for use in validate method
        if not hasattr(self, '_validated_receivers'):
            self._validated_receivers = {}
        self._validated_receivers[value] = receiver
        
        return value

    def validate(self, attrs):
        request_user = self.context['request'].user
        receiver_id = attrs['receiver_id']
        
        # Get receiver from cache if available, otherwise fetch it
        if hasattr(self, '_validated_receivers') and receiver_id in self._validated_receivers:
            receiver = self._validated_receivers[receiver_id]
        else:
            try:
                receiver = User.objects.get(id=receiver_id, is_active=True)
            except User.DoesNotExist:
                raise serializers.ValidationError({'receiver_id': f'User with ID {receiver_id} does not exist or is inactive.'})

        if request_user == receiver:
            raise serializers.ValidationError({'receiver_id': 'You cannot message yourself.'})

        # Check if there's an approved connection between sender and receiver
        connection_exists = UserConnection.objects.filter(
            Q(from_user=request_user, to_user=receiver) | Q(from_user=receiver, to_user=request_user),
            status=UserConnection.Status.APPROVED
        ).exists()

        if not connection_exists:
            raise serializers.ValidationError(
                {'receiver_id': 'You cannot message this user unless you are friends.'}
            )

        attrs['receiver'] = receiver
        attrs['sender'] = request_user
        return attrs

    def create(self, validated_data):
        return Message.objects.create(**validated_data)


class ConversationListSerializer(serializers.Serializer):
    """Serializer for listing conversations with latest message."""
    user = MessageUserSerializer()
    latest_message = MessageSerializer()
    unread_count = serializers.IntegerField()


class MessageMarkReadSerializer(serializers.Serializer):
    """Serializer for marking messages as read."""
    message_id = serializers.IntegerField(required=False)
    conversation_user_id = serializers.IntegerField(required=False)

    def validate(self, attrs):
        request_user = self.context['request'].user
        message_id = attrs.get('message_id')
        conversation_user_id = attrs.get('conversation_user_id')

        if not message_id and not conversation_user_id:
            raise serializers.ValidationError(
                'Either message_id or conversation_user_id must be provided.'
            )

        if message_id and conversation_user_id:
            raise serializers.ValidationError(
                'Provide either message_id or conversation_user_id, not both.'
            )

        if message_id:
            try:
                message = Message.objects.get(id=message_id, receiver=request_user)
            except Message.DoesNotExist:
                raise serializers.ValidationError({'message_id': 'Message not found.'})
            attrs['message'] = message

        if conversation_user_id:
            try:
                other_user = User.objects.get(id=conversation_user_id, is_active=True)
            except User.DoesNotExist:
                raise serializers.ValidationError(
                    {'conversation_user_id': 'User not found.'}
                )
            # Verify they are friends
            connection_exists = UserConnection.objects.filter(
                Q(from_user=request_user, to_user=other_user) | Q(from_user=other_user, to_user=request_user),
                status=UserConnection.Status.APPROVED
            ).exists()
            if not connection_exists:
                raise serializers.ValidationError(
                    {'conversation_user_id': 'You cannot mark messages as read for this user unless you are friends.'}
                )
            attrs['other_user'] = other_user

        return attrs


# Session Serializers
class SessionUserSerializer(serializers.ModelSerializer):
    """Serializer for user information in sessions."""
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name']


class SessionSerializer(serializers.ModelSerializer):
    """Serializer for viewing session details."""
    initiator_id = serializers.IntegerField(source='initiator.id', read_only=True)
    participant_id = serializers.IntegerField(source='participant.id', read_only=True)
    initiator = SessionUserSerializer(read_only=True)
    participant = SessionUserSerializer(read_only=True)

    class Meta:
        model = models.Session
        fields = [
            'id',
            'initiator_id',
            'initiator',
            'participant_id',
            'participant',
            'status',
            'zoom_meeting_id',
            'zoom_meeting_url',
            'zoom_meeting_password',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class SessionCreateSerializer(serializers.Serializer):
    """Serializer for creating a new session."""
    participant_id = serializers.IntegerField(required=True)

    def validate_participant_id(self, value):
        """Validate that the participant exists and is active."""
        try:
            participant = User.objects.get(id=value, is_active=True)
        except User.DoesNotExist:
            raise serializers.ValidationError(f'User with ID {value} does not exist or is inactive.')
        return value

    def validate(self, attrs):
        request_user = self.context['request'].user
        participant_id = attrs['participant_id']
        
        try:
            participant = User.objects.get(id=participant_id, is_active=True)
        except User.DoesNotExist:
            raise serializers.ValidationError({'participant_id': f'User with ID {participant_id} does not exist or is inactive.'})

        if request_user.id == participant_id:
            raise serializers.ValidationError({'participant_id': 'You cannot create a session with yourself.'})

        # Check if there's an approved connection (friends)
        connection_exists = models.UserConnection.objects.filter(
            Q(from_user=request_user, to_user=participant) | Q(from_user=participant, to_user=request_user),
            status=models.UserConnection.Status.APPROVED
        ).exists()

        if not connection_exists:
            raise serializers.ValidationError(
                {'participant_id': 'You can only create sessions with approved friends.'}
            )

        attrs['participant'] = participant
        attrs['initiator'] = request_user
        return attrs

    def create(self, validated_data):
        initiator = validated_data['initiator']
        participant = validated_data['participant']
        
        # Get subscription from context (passed from view with lock) or reload it
        # This ensures we use the same locked subscription object
        from django.db.models import F
        
        subscription = self.context.get('subscription')
        if not subscription:
            # Fallback: reload subscription (should not happen if view is correct)
            subscription = models.UserSubscription.objects.select_related('plan').get(user=initiator)
        
        # CRITICAL: Double-check subscription limit before creating session
        # This is a safety check to prevent any bypass
        max_sessions = subscription.plan.max_sessions
        sessions_used = subscription.sessions_used
        
        if max_sessions != -1:  # Not unlimited
            if sessions_used >= max_sessions:
                raise serializers.ValidationError(
                    {
                        'participant_id': f'Session limit exceeded. You have used {sessions_used} of {max_sessions} allowed sessions. Please upgrade your plan to create more sessions.'
                    }
                )
        
        # Only create session if limit check passes
        session = models.Session.objects.create(
            initiator=initiator,
            participant=participant,
            status=models.Session.Status.PENDING,
        )
        
        # Increment counter atomically (using F() expression for database-level increment)
        # Use the subscription ID to ensure we're updating the correct row
        updated_count = models.UserSubscription.objects.filter(
            id=subscription.id,
            user=initiator
        ).update(
            sessions_used=F('sessions_used') + 1
        )
        
        # Verify the update succeeded
        if updated_count != 1:
            # This should never happen, but if it does, we have a problem
            raise serializers.ValidationError(
                {
                    'participant_id': 'Failed to update session counter. Please try again.'
                }
            )
        
        # Create audit log
        models.SessionAuditLog.objects.create(
            session=session,
            user=initiator,
            event_type=models.SessionAuditLog.EventType.CREATED,
            message=f'Session created by {initiator.username}',
        )
        
        return session


class SessionStartSerializer(serializers.Serializer):
    """Serializer for starting a session (generating Zoom link)."""
    session_id = serializers.IntegerField()

    def validate_session_id(self, value):
        """Validate that the session exists."""
        try:
            session = models.Session.objects.select_related('initiator', 'participant').get(id=value)
        except models.Session.DoesNotExist:
            raise serializers.ValidationError(f'Session with ID {value} does not exist.')
        return value

    def validate(self, attrs):
        request_user = self.context['request'].user
        session_id = attrs['session_id']
        
        try:
            session = models.Session.objects.select_related('initiator', 'participant').get(id=session_id)
        except models.Session.DoesNotExist:
            raise serializers.ValidationError({'session_id': f'Session with ID {session_id} does not exist.'})

        # Verify user is a participant
        if request_user not in [session.initiator, session.participant]:
            raise serializers.ValidationError(
                {'session_id': 'You are not a participant in this session.'}
            )

        # Check session status
        if session.status != models.Session.Status.PENDING:
            raise serializers.ValidationError(
                {'session_id': f'Cannot start session. Current status: {session.status}.'}
            )

        attrs['session'] = session
        return attrs

    def save(self, **kwargs):
        from .zoom_helpers import create_zoom_meeting
        
        session = self.validated_data['session']
        request_user = self.context['request'].user
        
        # Generate Zoom meeting
        meeting_id, join_url, password = create_zoom_meeting(
            topic=f"Session: {session.initiator.username} & {session.participant.username}",
            duration_minutes=60,
        )
        
        # Update session
        session.zoom_meeting_id = meeting_id
        session.zoom_meeting_url = join_url
        session.zoom_meeting_password = password
        session.status = models.Session.Status.ACTIVE
        session.started_at = timezone.now()
        session.started_by = request_user
        session.save(update_fields=[
            'zoom_meeting_id',
            'zoom_meeting_url',
            'zoom_meeting_password',
            'status',
            'started_at',
            'started_by',
            'updated_at',
        ])
        
        # Create audit log
        models.SessionAuditLog.objects.create(
            session=session,
            user=request_user,
            event_type=models.SessionAuditLog.EventType.STARTED,
            message=f'Session started by {request_user.username}. Zoom link generated.',
            metadata={
                'zoom_meeting_id': meeting_id,
                'initiated_by': request_user.id,
            },
        )
        
        models.SessionAuditLog.objects.create(
            session=session,
            user=request_user,
            event_type=models.SessionAuditLog.EventType.ZOOM_LINK_GENERATED,
            message=f'Zoom meeting link generated: {join_url}',
            metadata={
                'zoom_meeting_id': meeting_id,
            },
        )
        
        return session


class SessionReadySerializer(serializers.Serializer):
    """Serializer for marking a participant as ready."""
    session_id = serializers.IntegerField()

    def validate_session_id(self, value):
        """Validate that the session exists."""
        try:
            session = models.Session.objects.select_related('initiator', 'participant').get(id=value)
        except models.Session.DoesNotExist:
            raise serializers.ValidationError(f'Session with ID {value} does not exist.')
        return value

    def validate(self, attrs):
        request_user = self.context['request'].user
        session_id = attrs['session_id']
        
        try:
            session = models.Session.objects.select_related('initiator', 'participant').get(id=session_id)
        except models.Session.DoesNotExist:
            raise serializers.ValidationError({'session_id': f'Session with ID {session_id} does not exist.'})

        # Verify user is a participant
        if request_user not in [session.initiator, session.participant]:
            raise serializers.ValidationError(
                {'session_id': 'You are not a participant in this session.'}
            )

        # Check session status
        if session.status != models.Session.Status.ACTIVE:
            raise serializers.ValidationError(
                {'session_id': f'Cannot mark ready. Session status: {session.status}.'}
            )

        attrs['session'] = session
        return attrs

    def save(self, **kwargs):
        session = self.validated_data['session']
        request_user = self.context['request'].user
        
        # Mark user as ready
        session.mark_ready(request_user)
        
        # Create audit log
        models.SessionAuditLog.objects.create(
            session=session,
            user=request_user,
            event_type=models.SessionAuditLog.EventType.READY,
            message=f'{request_user.username} is ready to join the session.',
        )
        
        return session


class SessionJoinTokenSerializer(serializers.Serializer):
    """Serializer for generating a join token."""
    session_id = serializers.IntegerField()

    def validate_session_id(self, value):
        """Validate that the session exists."""
        try:
            session = models.Session.objects.select_related('initiator', 'participant').get(id=value)
        except models.Session.DoesNotExist:
            raise serializers.ValidationError(f'Session with ID {value} does not exist.')
        return value

    def validate(self, attrs):
        request_user = self.context['request'].user
        session_id = attrs['session_id']
        
        try:
            session = models.Session.objects.select_related('initiator', 'participant').get(id=session_id)
        except models.Session.DoesNotExist:
            raise serializers.ValidationError({'session_id': f'Session with ID {session_id} does not exist.'})

        # Verify user is a participant
        if request_user not in [session.initiator, session.participant]:
            raise serializers.ValidationError(
                {'session_id': 'You are not a participant in this session.'}
            )

        # Check session status
        if session.status != models.Session.Status.ACTIVE:
            raise serializers.ValidationError(
                {'session_id': f'Cannot generate join token. Session status: {session.status}.'}
            )

        attrs['session'] = session
        return attrs

    def save(self, **kwargs):
        import secrets
        
        session = self.validated_data['session']
        request_user = self.context['request'].user
        
        # Generate secure token
        token = secrets.token_urlsafe(32)
        expires_at = timezone.now() + timedelta(hours=1)  # Token valid for 1 hour
        
        # Create join token
        join_token = models.SessionJoinToken.objects.create(
            session=session,
            user=request_user,
            token=token,
            expires_at=expires_at,
        )
        
        return join_token


class SessionJoinTokenValidateSerializer(serializers.Serializer):
    """Serializer for validating a join token."""
    token = serializers.CharField(max_length=64)

    def validate(self, attrs):
        token = attrs['token']
        
        try:
            join_token = models.SessionJoinToken.objects.select_related('session', 'user').get(token=token)
        except models.SessionJoinToken.DoesNotExist:
            raise serializers.ValidationError({'token': 'Invalid join token.'})

        if not join_token.is_valid():
            if join_token.is_used:
                raise serializers.ValidationError({'token': 'This join token has already been used.'})
            if join_token.is_expired():
                raise serializers.ValidationError({'token': 'This join token has expired.'})
            raise serializers.ValidationError({'token': 'Invalid join token.'})

        # Check if user can join
        if not join_token.session.can_join(join_token.user):
            raise serializers.ValidationError(
                {'token': 'You cannot join this session yet. The other participant must be ready.'}
            )

        attrs['join_token'] = join_token
        return attrs

    def save(self, **kwargs):
        join_token = self.validated_data['join_token']
        
        # Mark token as used
        join_token.is_used = True
        join_token.used_at = timezone.now()
        join_token.save(update_fields=['is_used', 'used_at'])
        
        # Create audit log
        models.SessionAuditLog.objects.create(
            session=join_token.session,
            user=join_token.user,
            event_type=models.SessionAuditLog.EventType.JOINED,
            message=f'{join_token.user.username} joined the session using token.',
        )
        
        return join_token.session


class SessionEndSerializer(serializers.Serializer):
    """Serializer for ending a session."""
    session_id = serializers.IntegerField()

    def validate_session_id(self, value):
        """Validate that the session exists."""
        try:
            session = models.Session.objects.select_related('initiator', 'participant').get(id=value)
        except models.Session.DoesNotExist:
            raise serializers.ValidationError(f'Session with ID {value} does not exist.')
        return value

    def validate(self, attrs):
        request_user = self.context['request'].user
        session_id = attrs['session_id']
        
        try:
            session = models.Session.objects.select_related('initiator', 'participant').get(id=session_id)
        except models.Session.DoesNotExist:
            raise serializers.ValidationError({'session_id': f'Session with ID {session_id} does not exist.'})

        # Verify user is a participant
        if request_user not in [session.initiator, session.participant]:
            raise serializers.ValidationError(
                {'session_id': 'You are not a participant in this session.'}
            )

        # Check session status
        if session.status not in [models.Session.Status.ACTIVE, models.Session.Status.PENDING]:
            raise serializers.ValidationError(
                {'session_id': f'Cannot end session. Current status: {session.status}.'}
            )

        attrs['session'] = session
        return attrs

    def save(self, **kwargs):
        session = self.validated_data['session']
        request_user = self.context['request'].user
        
        # Update session
        session.status = models.Session.Status.COMPLETED
        session.ended_at = timezone.now()
        session.save(update_fields=['status', 'ended_at', 'updated_at'])
        
        # Create audit log
        models.SessionAuditLog.objects.create(
            session=session,
            user=request_user,
            event_type=models.SessionAuditLog.EventType.ENDED,
            message=f'Session ended by {request_user.username}.',
        )
        
        return session


class SessionCancelSerializer(serializers.Serializer):
    """Serializer for cancelling a session."""
    session_id = serializers.IntegerField()

    def validate_session_id(self, value):
        """Validate that the session exists."""
        try:
            session = models.Session.objects.select_related('initiator', 'participant').get(id=value)
        except models.Session.DoesNotExist:
            raise serializers.ValidationError(f'Session with ID {value} does not exist.')
        return value

    def validate(self, attrs):
        request_user = self.context['request'].user
        session_id = attrs['session_id']
        
        try:
            session = models.Session.objects.select_related('initiator', 'participant').get(id=session_id)
        except models.Session.DoesNotExist:
            raise serializers.ValidationError({'session_id': f'Session with ID {session_id} does not exist.'})

        # Verify user is a participant
        if request_user not in [session.initiator, session.participant]:
            raise serializers.ValidationError(
                {'session_id': 'You are not a participant in this session.'}
            )

        # Check session status
        if session.status == models.Session.Status.CANCELLED:
            raise serializers.ValidationError(
                {'session_id': 'Session is already cancelled.'}
            )
        if session.status == models.Session.Status.COMPLETED:
            raise serializers.ValidationError(
                {'session_id': 'Cannot cancel a completed session.'}
            )

        attrs['session'] = session
        return attrs

    def save(self, **kwargs):
        session = self.validated_data['session']
        request_user = self.context['request'].user
        
        # Update session
        session.status = models.Session.Status.CANCELLED
        if not session.ended_at:
            session.ended_at = timezone.now()
        session.save(update_fields=['status', 'ended_at', 'updated_at'])
        
        # Create audit log
        models.SessionAuditLog.objects.create(
            session=session,
            user=request_user,
            event_type=models.SessionAuditLog.EventType.CANCELLED,
            message=f'Session cancelled by {request_user.username}.',
        )
        
        return session


class SessionAuditLogSerializer(serializers.ModelSerializer):
    """Serializer for session audit logs."""
    user = SessionUserSerializer(read_only=True)

    class Meta:
        model = models.SessionAuditLog
        fields = [
            'id',
            'user',
            'event_type',
            'message',
            'metadata',
            'created_at',
        ]
        read_only_fields = fields


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    """Serializer for subscription plans."""
    
    class Meta:
        model = SubscriptionPlan
        fields = [
            'id',
            'tier',
            'name',
            'description',
            'price',
            'duration_days',
            'max_profile_views',
            'max_connections',
            'max_connection_requests',
            'max_chat_users',
            'max_sessions',
            'can_send_messages',
            'can_view_photos',
            'can_see_who_viewed',
            'priority_support',
            'advanced_search',
            'verified_badge',
            'is_active',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class UserSubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for user subscriptions."""
    plan = SubscriptionPlanSerializer(read_only=True)
    plan_id = serializers.IntegerField(write_only=True, required=False)
    days_remaining = serializers.SerializerMethodField()
    is_active_display = serializers.SerializerMethodField()
    
    class Meta:
        model = UserSubscription
        fields = [
            'id',
            'user',
            'plan',
            'plan_id',
            'status',
            'started_at',
            'expires_at',
            'auto_renew',
            'cancelled_at',
            'cancellation_reason',
            'profile_views_used',
            'connections_used',
            'connection_requests_used',
            'chat_users_count',
            'sessions_used',
            'last_reset_at',
            'days_remaining',
            'is_active_display',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'user',
            'plan',
            'status',
            'started_at',
            'expires_at',
            'cancelled_at',
            'profile_views_used',
            'connections_used',
            'connection_requests_used',
            'chat_users_count',
            'sessions_used',
            'last_reset_at',
            'created_at',
            'updated_at',
        ]
    
    def get_days_remaining(self, obj):
        """Get days remaining in subscription."""
        return obj.days_remaining
    
    def get_is_active_display(self, obj):
        """Get if subscription is active."""
        return obj.is_active


class SubscriptionUpgradeSerializer(serializers.Serializer):
    """Serializer for subscribing/upgrading to a plan."""
    plan_id = serializers.IntegerField(required=True)
    auto_renew = serializers.BooleanField(default=False, required=False)
    
    def validate_plan_id(self, value):
        """Validate that the plan exists and is active."""
        try:
            plan = SubscriptionPlan.objects.get(id=value, is_active=True)
        except SubscriptionPlan.DoesNotExist:
            raise serializers.ValidationError('Subscription plan not found or inactive.')
        return value


class UserReportSerializer(serializers.Serializer):
    """Serializer for creating user reports."""
    reported_user_id = serializers.IntegerField(required=True)
    reason = serializers.ChoiceField(
        choices=UserReport.ReportReason.choices,
        required=True,
    )
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=1000,
    )

    def validate_reported_user_id(self, value):
        """Validate that the reported user exists."""
        try:
            reported_user = User.objects.get(id=value, is_active=True)
        except User.DoesNotExist:
            raise serializers.ValidationError('User not found or inactive.')
        return value

    def validate(self, attrs):
        request_user = self.context['request'].user
        reported_user_id = attrs.get('reported_user_id')
        
        if not reported_user_id:
            raise serializers.ValidationError({'reported_user_id': 'This field is required.'})
        
        try:
            reported_user = User.objects.get(id=reported_user_id, is_active=True)
        except User.DoesNotExist:
            raise serializers.ValidationError({'reported_user_id': 'User not found or inactive.'})
        
        if request_user.id == reported_user_id:
            raise serializers.ValidationError({'reported_user_id': 'You cannot report yourself.'})
        
        # Check if user has already reported this user
        existing_report = UserReport.objects.filter(
            reporter=request_user,
            reported_user=reported_user,
            status='pending'
        ).exists()
        
        if existing_report:
            raise serializers.ValidationError(
                {'reported_user_id': 'You have already reported this user. Please wait for admin review.'}
            )
        
        attrs['reported_user'] = reported_user
        return attrs

    def create(self, validated_data):
        request_user = self.context['request'].user
        reported_user = validated_data['reported_user']
        reason = validated_data['reason']
        description = validated_data.get('description', '')
        
        return UserReport.objects.create(
            reporter=request_user,
            reported_user=reported_user,
            reason=reason,
            description=description,
            status='pending',
        )
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
from django.http import QueryDict
from django.utils import timezone
from rest_framework import serializers

from .models import PasswordResetOTP, UserProfile


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
            try:
                user = User.objects.get(email__iexact=email)
            except User.DoesNotExist:
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
                ],
            ),
        ]
    )
    profile_picture = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = UserProfile
        fields = [
            'candidate_name',
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
        ]

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

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        request = self.context.get('request')
        picture = rep.get('profile_picture')
        if picture and request is not None:
            rep['profile_picture'] = request.build_absolute_uri(picture)

        sectioned = OrderedDict()
        for section, fields in self.section_field_map.items():
            sectioned[section] = {field: rep.pop(field, None) for field in fields}

        sectioned['meta'] = {
            'profile_id': instance.id,
            'user_id': instance.user_id,
            'created_at': instance.created_at.isoformat(),
            'updated_at': instance.updated_at.isoformat(),
        }
        return sectioned


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
            'profile_picture',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        request = self.context.get('request')
        picture = rep.get('profile_picture')
        if picture and request is not None:
            rep['profile_picture'] = request.build_absolute_uri(picture)
        return rep
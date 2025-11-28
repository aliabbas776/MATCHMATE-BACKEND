from django.contrib import admin

from .models import (
    CNICVerification,
    MatchPreference,
    Message,
    PasswordResetOTP,
    Session,
    SessionAuditLog,
    SessionJoinToken,
    UserConnection,
    UserProfile,
)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'candidate_name',
        'city',
        'gender',
        'marital_status',
        'phone_number',
        'is_public',
        'updated_at',
    )
    search_fields = ('user__username', 'user__email', 'candidate_name', 'city', 'phone_number')
    list_filter = ('gender', 'marital_status', 'country', 'city')

    fieldsets = (
        ('Account', {'fields': ('user', 'profile_picture', 'blur_photo', 'is_public')}),
        (
            'Candidate Information',
            {
                'fields': (
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
                )
            },
        ),
        (
            'Profile Details',
            {'fields': ('profile_for', 'gender', 'marital_status')},
        ),
        (
            'Family Details',
            {
                'fields': (
                    'father_status',
                    'father_employment_status',
                    'mother_status',
                    'mother_employment_status',
                    'total_brothers',
                    'total_sisters',
                )
            },
        ),
        (
            'Education & Employment',
            {'fields': ('education_level', 'employment_status', 'profession')},
        ),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )
    readonly_fields = ('created_at', 'updated_at')


@admin.register(PasswordResetOTP)
class PasswordResetOTPAdmin(admin.ModelAdmin):
    list_display = ('user', 'code', 'is_used', 'expires_at', 'created_at')
    search_fields = ('user__email', 'code')
    list_filter = ('is_used',)


@admin.register(UserConnection)
class UserConnectionAdmin(admin.ModelAdmin):
    list_display = ('from_user', 'to_user', 'status', 'created_at', 'updated_at')
    list_filter = ('status',)
    search_fields = ('from_user__username', 'to_user__username', 'from_user__email', 'to_user__email')


@admin.register(CNICVerification)
class CNICVerificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'status', 'extracted_full_name', 'extracted_cnic', 'tampering_detected', 'blur_score', 'updated_at')
    list_filter = ('status', 'tampering_detected')
    search_fields = ('user__username', 'user__email', 'extracted_full_name', 'extracted_cnic')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('User Information', {'fields': ('user',)}),
        ('CNIC Images', {'fields': ('front_image', 'back_image')}),
        ('Extracted Data', {
            'fields': (
                'extracted_full_name',
                'extracted_cnic',
                'extracted_dob',
                'extracted_gender',
            )
        }),
        ('Verification Status', {
            'fields': (
                'status',
                'rejection_reason',
                'tampering_detected',
                'blur_score',
            )
        }),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )


@admin.register(MatchPreference)
class MatchPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'status', 'religion', 'caste', 'city', 'min_age', 'max_age', 'updated_at')
    list_filter = ('status', 'religion', 'caste', 'country', 'city', 'employment_status')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('updated_at',)
    
    fieldsets = (
        ('User', {'fields': ('user',)}),
        ('Basic Preferences', {
            'fields': (
                'status',
                'religion',
                'caste',
            )
        }),
        ('Location', {
            'fields': (
                'country',
                'city',
            )
        }),
        ('Employment', {
            'fields': (
                'employment_status',
                'profession',
            )
        }),
        ('Age Range', {
            'fields': (
                'min_age',
                'max_age',
            )
        }),
        ('Other Preferences', {
            'fields': ('prefers_disability',)
        }),
        ('Timestamps', {'fields': ('updated_at',), 'classes': ('collapse',)}),
    )


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'receiver', 'content_preview', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('sender__username', 'receiver__username', 'content')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Message', {'fields': ('sender', 'receiver', 'content', 'is_read')}),
        ('Timestamps', {'fields': ('created_at',), 'classes': ('collapse',)}),
    )
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content'


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'initiator',
        'participant',
        'started_by',
        'status',
        'initiator_ready',
        'participant_ready',
        'started_at',
        'ended_at',
        'created_at',
    )
    list_filter = ('status', 'initiator_ready', 'participant_ready', 'created_at', 'started_at')
    search_fields = (
        'initiator__username',
        'initiator__email',
        'participant__username',
        'participant__email',
        'zoom_meeting_id',
    )
    readonly_fields = ('created_at', 'updated_at', 'started_at', 'ended_at')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Participants', {'fields': ('initiator', 'participant', 'started_by')}),
        ('Status', {
            'fields': (
                'status',
                'initiator_ready',
                'participant_ready',
            )
        }),
        ('Zoom Meeting', {
            'fields': (
                'zoom_meeting_id',
                'zoom_meeting_url',
                'zoom_meeting_password',
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'started_at', 'ended_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(SessionJoinToken)
class SessionJoinTokenAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'session',
        'user',
        'token_preview',
        'is_used',
        'expires_at',
        'created_at',
        'used_at',
    )
    list_filter = ('is_used', 'expires_at', 'created_at')
    search_fields = (
        'session__id',
        'user__username',
        'user__email',
        'token',
    )
    readonly_fields = ('created_at', 'used_at')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Token Information', {'fields': ('session', 'user', 'token')}),
        ('Status', {'fields': ('is_used', 'expires_at', 'used_at')}),
        ('Timestamps', {'fields': ('created_at',), 'classes': ('collapse',)}),
    )
    
    def token_preview(self, obj):
        return obj.token[:20] + '...' if len(obj.token) > 20 else obj.token
    token_preview.short_description = 'Token'


@admin.register(SessionAuditLog)
class SessionAuditLogAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'session',
        'user',
        'event_type',
        'message_preview',
        'created_at',
    )
    list_filter = ('event_type', 'created_at')
    search_fields = (
        'session__id',
        'user__username',
        'user__email',
        'message',
        'event_type',
    )
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Session Information', {'fields': ('session', 'user')}),
        ('Event Details', {'fields': ('event_type', 'message', 'metadata')}),
        ('Timestamps', {'fields': ('created_at',), 'classes': ('collapse',)}),
    )
    
    def message_preview(self, obj):
        return obj.message[:50] + '...' if len(obj.message) > 50 else obj.message
    message_preview.short_description = 'Message'

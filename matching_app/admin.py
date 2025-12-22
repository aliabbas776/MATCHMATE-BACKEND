from django.contrib import admin

from .models import (
    CNICVerification,
    MatchPreference,
    Message,
    PasswordResetOTP,
    Session,
    SessionAuditLog,
    SessionJoinToken,
    SubscriptionPlan,
    UserConnection,
    UserProfile,
    UserReport,
    UserSubscription,
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
        'is_disabled',
        'updated_at',
    )
    search_fields = ('user__username', 'user__email', 'candidate_name', 'city', 'phone_number')
    list_filter = ('gender', 'marital_status', 'country', 'city', 'is_disabled', 'is_public')

    fieldsets = (
        ('Account', {'fields': ('user', 'profile_picture', 'blur_photo', 'is_public', 'is_disabled', 'disabled_at', 'disabled_reason')}),
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
    readonly_fields = ('created_at', 'updated_at', 'disabled_at')


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
    actions = ['sync_status_to_profile']
    
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
    
    def save_model(self, request, obj, form, change):
        """Override save_model to ensure status sync happens."""
        # Store old status before saving
        old_status = None
        if change and obj.pk:
            try:
                old_instance = CNICVerification.objects.get(pk=obj.pk)
                old_status = old_instance.status
            except CNICVerification.DoesNotExist:
                pass
        
        # Save the model (this will trigger the signal)
        super().save_model(request, obj, form, change)
        
        # Manually trigger sync if signal didn't fire (backup)
        if change and old_status != obj.status:
            try:
                profile = obj.user.profile
                from django.utils import timezone
                
                status_mapping = {
                    CNICVerification.Status.PENDING: 'pending',
                    CNICVerification.Status.VERIFIED: 'verified',
                    CNICVerification.Status.REJECTED: 'rejected',
                }
                
                new_status = status_mapping.get(obj.status, 'unverified')
                
                if profile.cnic_verification_status != new_status:
                    profile.cnic_verification_status = new_status
                    
                    if obj.status == CNICVerification.Status.VERIFIED:
                        profile.cnic_verified_at = timezone.now()
                    elif obj.status == CNICVerification.Status.REJECTED:
                        profile.cnic_verified_at = None
                    
                    profile.save(update_fields=['cnic_verification_status', 'cnic_verified_at'])
            except UserProfile.DoesNotExist:
                pass
    
    def sync_status_to_profile(self, request, queryset):
        """Admin action to manually sync CNIC verification status to UserProfile."""
        from django.utils import timezone
        synced_count = 0
        skipped_count = 0
        
        for cnic_verification in queryset:
            try:
                profile = cnic_verification.user.profile
                # Map CNICVerification status to UserProfile status
                status_mapping = {
                    CNICVerification.Status.PENDING: 'pending',
                    CNICVerification.Status.VERIFIED: 'verified',
                    CNICVerification.Status.REJECTED: 'rejected',
                }
                
                new_status = status_mapping.get(cnic_verification.status, 'unverified')
                
                if profile.cnic_verification_status != new_status:
                    profile.cnic_verification_status = new_status
                    
                    # Update verified_at timestamp
                    if cnic_verification.status == CNICVerification.Status.VERIFIED:
                        profile.cnic_verified_at = timezone.now()
                    elif cnic_verification.status == CNICVerification.Status.REJECTED:
                        profile.cnic_verified_at = None
                    
                    profile.save(update_fields=['cnic_verification_status', 'cnic_verified_at'])
                    synced_count += 1
                else:
                    skipped_count += 1
            except UserProfile.DoesNotExist:
                pass
        
        self.message_user(
            request,
            f'Successfully synced {synced_count} profile(s). {skipped_count} already synced.'
        )
    
    sync_status_to_profile.short_description = 'Sync status to UserProfile'


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


@admin.register(UserReport)
class UserReportAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'reporter',
        'reported_user',
        'reason',
        'status',
        'description_preview',
        'reviewed_by',
        'reviewed_at',
        'created_at',
    )
    list_filter = ('status', 'reason', 'created_at', 'reviewed_at')
    search_fields = (
        'reporter__username',
        'reporter__email',
        'reported_user__username',
        'reported_user__email',
        'description',
    )
    readonly_fields = ('created_at', 'updated_at', 'reviewed_at')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Report Information', {
            'fields': (
                'reporter',
                'reported_user',
                'reason',
                'description',
            )
        }),
        ('Review Status', {
            'fields': (
                'status',
                'reviewed_by',
                'reviewed_at',
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def description_preview(self, obj):
        return obj.description[:50] + '...' if obj.description and len(obj.description) > 50 else (obj.description or '-')
    description_preview.short_description = 'Description'
    
    def save_model(self, request, obj, form, change):
        """Override save_model to ensure disable/enable logic runs when status changes."""
        # Get old status if updating
        old_status = None
        if change and obj.pk:
            try:
                old_obj = UserReport.objects.get(pk=obj.pk)
                old_status = old_obj.status
            except UserReport.DoesNotExist:
                pass
        
        # Save the model (this will trigger the save() method)
        super().save_model(request, obj, form, change)
        
        # If status changed, manually trigger the check (in case save() didn't catch it)
        if old_status != obj.status:
            from django.db.models import Count
            from django.db import transaction
            from matching_app.models import UserProfile
            from django.utils import timezone
            
            # Count current pending reports
            pending_count = UserReport.objects.filter(
                reported_user=obj.reported_user,
                status='pending'
            ).aggregate(
                distinct_count=Count('reporter', distinct=True)
            )['distinct_count']
            
            try:
                profile = UserProfile.objects.get(user=obj.reported_user)
                
                # If status changed TO pending and pending reports >= 5, disable
                if obj.status == 'pending' and pending_count >= 5:
                    if not profile.is_disabled:
                        with transaction.atomic():
                            profile.is_disabled = True
                            profile.disabled_at = timezone.now()
                            profile.disabled_reason = f'Profile disabled automatically after being reported by {pending_count} different users.'
                            profile.save(update_fields=['is_disabled', 'disabled_at', 'disabled_reason', 'updated_at'])
                            
                            obj.reported_user.is_active = False
                            obj.reported_user.save(update_fields=['is_active'])
                
                # If status changed FROM pending and pending reports < 5, re-enable
                elif old_status == 'pending' and obj.status in ['dismissed', 'reviewed']:
                    if pending_count < 5 and profile.is_disabled:
                        with transaction.atomic():
                            profile.is_disabled = False
                            profile.disabled_reason = ''
                            profile.save(update_fields=['is_disabled', 'disabled_reason', 'updated_at'])
                            
                            obj.reported_user.is_active = True
                            obj.reported_user.save(update_fields=['is_active'])
            except UserProfile.DoesNotExist:
                pass
    
    actions = ['mark_as_reviewed', 'mark_as_dismissed', 'mark_as_pending']
    
    def mark_as_reviewed(self, request, queryset):
        """Mark selected reports as reviewed."""
        from django.utils import timezone
        from django.db.models import Count
        from matching_app.models import UserProfile
        
        # Get all reported users BEFORE updating (to know which users to check)
        pending_reports = queryset.filter(status='pending')
        reported_users = set(pending_reports.values_list('reported_user', flat=True).distinct())
        
        # Update the reports
        updated = pending_reports.update(
            status='reviewed',
            reviewed_by=request.user,
            reviewed_at=timezone.now()
        )
        
        # Check and re-enable profiles AFTER update
        re_enabled_count = 0
        for reported_user_id in reported_users:
            try:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                reported_user = User.objects.get(id=reported_user_id)
                
                # Count remaining pending reports AFTER the update
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
                            profile.is_disabled = False
                            profile.disabled_reason = ''
                            profile.save(update_fields=['is_disabled', 'disabled_reason', 'updated_at'])
                            
                            reported_user.is_active = True
                            reported_user.save(update_fields=['is_active'])
                            re_enabled_count += 1
                    except UserProfile.DoesNotExist:
                        pass
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error re-enabling profile for user {reported_user_id}: {str(e)}")
        
        message = f'{updated} report(s) marked as reviewed.'
        if re_enabled_count > 0:
            message += f' {re_enabled_count} user profile(s) have been re-enabled.'
        self.message_user(request, message)
    mark_as_reviewed.short_description = 'Mark selected reports as reviewed'
    
    def mark_as_dismissed(self, request, queryset):
        """Mark selected reports as dismissed."""
        from django.utils import timezone
        from django.db.models import Count
        from matching_app.models import UserProfile
        
        # Get all reported users BEFORE updating (to know which users to check)
        pending_reports = queryset.filter(status='pending')
        reported_users = set(pending_reports.values_list('reported_user', flat=True).distinct())
        
        # Update the reports
        updated = pending_reports.update(
            status='dismissed',
            reviewed_by=request.user,
            reviewed_at=timezone.now()
        )
        
        # Check and re-enable profiles AFTER update
        re_enabled_count = 0
        for reported_user_id in reported_users:
            try:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                reported_user = User.objects.get(id=reported_user_id)
                
                # Count remaining pending reports AFTER the update
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
                            profile.is_disabled = False
                            profile.disabled_reason = ''
                            profile.save(update_fields=['is_disabled', 'disabled_reason', 'updated_at'])
                            
                            reported_user.is_active = True
                            reported_user.save(update_fields=['is_active'])
                            re_enabled_count += 1
                    except UserProfile.DoesNotExist:
                        pass
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error re-enabling profile for user {reported_user_id}: {str(e)}")
        
        message = f'{updated} report(s) marked as dismissed.'
        if re_enabled_count > 0:
            message += f' {re_enabled_count} user profile(s) have been re-enabled.'
        self.message_user(request, message)
    mark_as_dismissed.short_description = 'Mark selected reports as dismissed'
    
    def mark_as_pending(self, request, queryset):
        """Mark selected reports as pending (re-open them)."""
        from django.db.models import Count
        from matching_app.models import UserProfile
        from django.utils import timezone
        
        # Get all reported users BEFORE updating
        non_pending_reports = queryset.exclude(status='pending')
        reported_users = set(non_pending_reports.values_list('reported_user', flat=True).distinct())
        
        # Update the reports
        updated = non_pending_reports.update(
            status='pending',
            reviewed_by=None,
            reviewed_at=None
        )
        
        # Check and disable profiles AFTER update if pending reports >= 5
        disabled_count = 0
        for reported_user_id in reported_users:
            try:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                reported_user = User.objects.get(id=reported_user_id)
                
                # Count pending reports AFTER the update
                pending_count = UserReport.objects.filter(
                    reported_user=reported_user,
                    status='pending'
                ).aggregate(
                    distinct_count=Count('reporter', distinct=True)
                )['distinct_count']
                
                # If pending reports >= 5, disable the profile
                if pending_count >= 5:
                    try:
                        profile = UserProfile.objects.get(user=reported_user)
                        if not profile.is_disabled:
                            profile.is_disabled = True
                            profile.disabled_at = timezone.now()
                            profile.disabled_reason = f'Profile disabled automatically after being reported by {pending_count} different users.'
                            profile.save(update_fields=['is_disabled', 'disabled_at', 'disabled_reason', 'updated_at'])
                            
                            reported_user.is_active = False
                            reported_user.save(update_fields=['is_active'])
                            disabled_count += 1
                    except UserProfile.DoesNotExist:
                        pass
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error disabling profile for user {reported_user_id}: {str(e)}")
        
        message = f'{updated} report(s) marked as pending.'
        if disabled_count > 0:
            message += f' {disabled_count} user profile(s) have been disabled due to 5+ pending reports.'
        self.message_user(request, message)
    mark_as_pending.short_description = 'Mark selected reports as pending (re-open)'


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = (
        'tier',
        'name',
        'price',
        'duration_days',
        'max_profile_views',
        'max_connections',
        'is_active',
        'created_at',
    )
    list_filter = ('tier', 'is_active', 'created_at')
    search_fields = ('name', 'tier', 'description')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'tier',
                'name',
                'description',
                'price',
                'duration_days',
                'is_active',
            )
        }),
        ('Limits', {
            'fields': (
                'max_profile_views',
                'max_connections',
                'max_connection_requests',
                'max_chat_users',
                'max_sessions',
            )
        }),
        ('Features', {
            'fields': (
                'can_send_messages',
                'can_view_photos',
                'can_see_who_viewed',
                'priority_support',
                'advanced_search',
                'verified_badge',
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'profile_views_used',
        'connections_used',
        'chat_users_count',
        'sessions_used',
    )
    list_filter = ('plan', 'status')
    search_fields = (
        'user__username',
        'user__email',
    )
    readonly_fields = (
        'user',
    )
    
    fieldsets = (
        ('Usage Tracking', {
            'fields': (
                'user',
                'profile_views_used',
                'connections_used',
                'connection_requests_used',
                'chat_users_count',
                'sessions_used',
            )
        }),
    )
    
    actions = ['reset_usage']
    
    def reset_usage(self, request, queryset):
        """Reset usage counters for selected subscriptions."""
        count = 0
        for subscription in queryset:
            subscription.reset_usage()
            count += 1
        self.message_user(request, f'Usage reset for {count} subscription(s).')
    reset_usage.short_description = 'Reset usage counters'

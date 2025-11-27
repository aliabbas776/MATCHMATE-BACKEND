from django.contrib import admin

from .models import PasswordResetOTP, UserConnection, UserProfile


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

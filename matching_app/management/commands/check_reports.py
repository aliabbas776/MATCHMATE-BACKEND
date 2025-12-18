"""
Management command to check report counts and manually disable profiles if needed.
Usage: python manage.py check_reports [--user-id USER_ID] [--disable]
"""
from django.core.management.base import BaseCommand
from django.db.models import Count
from django.contrib.auth import get_user_model
from matching_app.models import UserProfile, UserReport
from django.utils import timezone

User = get_user_model()


class Command(BaseCommand):
    help = 'Check report counts for users and optionally disable profiles with 5+ reports'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user-id',
            type=int,
            help='Check specific user by ID',
        )
        parser.add_argument(
            '--disable',
            action='store_true',
            help='Actually disable profiles that meet the criteria',
        )
        parser.add_argument(
            '--fix-disabled',
            action='store_true',
            help='Re-enable profiles that should not be disabled (have < 5 pending reports)',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Check all users',
        )

    def handle(self, *args, **options):
        user_id = options.get('user_id')
        disable = options.get('disable', False)
        check_all = options.get('all', False)
        fix_disabled = options.get('fix_disabled', False)

        if user_id:
            users = User.objects.filter(id=user_id)
        elif check_all:
            users = User.objects.all()
        else:
            self.stdout.write(self.style.ERROR('Please specify --user-id USER_ID or --all'))
            return

        for user in users:
            try:
                profile = UserProfile.objects.get(user=user)
            except UserProfile.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'User {user.id} ({user.username}) has no profile'))
                continue

            # Count distinct reporters
            report_info = UserReport.objects.filter(
                reported_user=user,
                status='pending'
            ).aggregate(
                total_reports=Count('id'),
                distinct_reporters=Count('reporter', distinct=True)
            )

            total_reports = report_info['total_reports']
            distinct_reporters = report_info['distinct_reporters']

            self.stdout.write(
                f'\nUser ID: {user.id} | Username: {user.username} | Email: {user.email}'
            )
            self.stdout.write(f'  Total pending reports: {total_reports}')
            self.stdout.write(f'  Distinct reporters: {distinct_reporters}')
            self.stdout.write(f'  Profile disabled: {profile.is_disabled}')
            self.stdout.write(f'  User active: {user.is_active}')

            if distinct_reporters >= 5:
                if profile.is_disabled:
                    self.stdout.write(self.style.WARNING('  ✓ Profile already disabled'))
                else:
                    if disable:
                        profile.is_disabled = True
                        profile.disabled_at = timezone.now()
                        profile.disabled_reason = f'Profile disabled automatically after being reported by {distinct_reporters} different users (via management command).'
                        profile.save(update_fields=['is_disabled', 'disabled_at', 'disabled_reason', 'updated_at'])
                        
                        user.is_active = False
                        user.save(update_fields=['is_active'])
                        
                        self.stdout.write(self.style.SUCCESS(f'  ✓ Profile DISABLED (had {distinct_reporters} distinct reporters)'))
                    else:
                        self.stdout.write(
                            self.style.WARNING(
                                f'  ⚠ Profile should be disabled (has {distinct_reporters} distinct reporters). Use --disable to disable.'
                            )
                        )
            else:
                self.stdout.write(f'  ✓ Profile OK (needs 5 distinct reporters, has {distinct_reporters})')
        
        # Fix disabled profiles that shouldn't be disabled
        if fix_disabled:
            self.stdout.write('\n=== Fixing Disabled Profiles ===')
            disabled_profiles = UserProfile.objects.filter(is_disabled=True)
            fixed_count = 0
            
            for profile in disabled_profiles:
                user = profile.user
                pending_count = UserReport.objects.filter(
                    reported_user=user,
                    status='pending'
                ).aggregate(
                    distinct_count=Count('reporter', distinct=True)
                )['distinct_count']
                
                if pending_count < 5:
                    profile.is_disabled = False
                    profile.disabled_reason = ''
                    profile.save(update_fields=['is_disabled', 'disabled_reason', 'updated_at'])
                    
                    user.is_active = True
                    user.save(update_fields=['is_active'])
                    
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  ✓ Re-enabled profile for user {user.id} ({user.username}) - had {pending_count} pending reports'
                        )
                    )
                    fixed_count += 1
            
            if fixed_count == 0:
                self.stdout.write(self.style.SUCCESS('  No profiles needed fixing.'))
            else:
                self.stdout.write(self.style.SUCCESS(f'\n✓ Fixed {fixed_count} profile(s).'))


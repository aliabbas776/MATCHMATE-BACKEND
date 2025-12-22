"""
Management command to sync CNIC verification status from CNICVerification to UserProfile.
Usage: python manage.py sync_cnic_status
"""
from django.core.management.base import BaseCommand
from matching_app.models import CNICVerification, UserProfile
from django.utils import timezone


class Command(BaseCommand):
    help = 'Sync CNIC verification status from CNICVerification to UserProfile'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user',
            type=str,
            help='Username to sync (optional, syncs all if not provided)',
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='User ID to sync',
        )
        parser.add_argument(
            '--profile-id',
            type=int,
            help='Profile ID to sync',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force sync even if status appears to match',
        )

    def handle(self, *args, **options):
        username = options.get('user')
        user_id = options.get('user_id')
        profile_id = options.get('profile_id')
        force = options.get('force', False)
        
        if username:
            # Sync specific user by username
            try:
                cnic_verification = CNICVerification.objects.get(user__username=username)
                if self.sync_status(cnic_verification, force=force):
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ Synced CNIC status for user: {username}')
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f'- Status already synced for user: {username}')
                    )
            except CNICVerification.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'✗ CNIC verification not found for user: {username}')
                )
        elif user_id:
            # Sync by user ID
            try:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                user = User.objects.get(id=user_id)
                cnic_verification = CNICVerification.objects.get(user=user)
                if self.sync_status(cnic_verification, force=force):
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ Synced CNIC status for user ID: {user_id} ({user.username})')
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f'- Status already synced for user ID: {user_id} ({user.username})')
                    )
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'✗ User not found with ID: {user_id}')
                )
            except CNICVerification.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'✗ CNIC verification not found for user ID: {user_id}')
                )
        elif profile_id:
            # Sync by profile ID
            try:
                profile = UserProfile.objects.get(id=profile_id)
                cnic_verification = CNICVerification.objects.get(user=profile.user)
                if self.sync_status(cnic_verification, force=force):
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ Synced CNIC status for profile ID: {profile_id} (user: {profile.user.username})')
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f'- Status already synced for profile ID: {profile_id} (user: {profile.user.username})')
                    )
            except UserProfile.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'✗ Profile not found with ID: {profile_id}')
                )
            except CNICVerification.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'✗ CNIC verification not found for profile ID: {profile_id}')
                )
        else:
            # Sync all users
            cnic_verifications = CNICVerification.objects.all()
            synced_count = 0
            skipped_count = 0
            
            for cnic_verification in cnic_verifications:
                if self.sync_status(cnic_verification, force=force):
                    synced_count += 1
                else:
                    skipped_count += 1
            
            self.stdout.write(self.style.SUCCESS(
                f'\n=== Summary ===\n'
                f'Synced: {synced_count} user(s)\n'
                f'Skipped: {skipped_count} user(s)\n'
                f'Total: {cnic_verifications.count()} CNIC verification(s)'
            ))
    
    def sync_status(self, cnic_verification, force=False):
        """Sync CNIC verification status to UserProfile."""
        try:
            profile = cnic_verification.user.profile
            # Map CNICVerification status to UserProfile status
            status_mapping = {
                CNICVerification.Status.PENDING: 'pending',
                CNICVerification.Status.VERIFIED: 'verified',
                CNICVerification.Status.REJECTED: 'rejected',
            }
            
            new_status = status_mapping.get(cnic_verification.status, 'unverified')
            old_status = profile.cnic_verification_status
            
            # Check if update is needed
            if force or profile.cnic_verification_status != new_status:
                profile.cnic_verification_status = new_status
                
                # Update verified_at timestamp
                if cnic_verification.status == CNICVerification.Status.VERIFIED:
                    profile.cnic_verified_at = timezone.now()
                elif cnic_verification.status == CNICVerification.Status.REJECTED:
                    profile.cnic_verified_at = None
                
                profile.save(update_fields=['cnic_verification_status', 'cnic_verified_at'])
                if old_status != new_status:
                    self.stdout.write(
                        f'  → Updated {cnic_verification.user.username}: '
                        f'{old_status} → {new_status}'
                    )
                else:
                    self.stdout.write(
                        f'  → Force updated {cnic_verification.user.username}: '
                        f'{new_status}'
                    )
                return True
            else:
                self.stdout.write(
                    f'  - Skipped {cnic_verification.user.username}: '
                    f'status already synced ({new_status})'
                )
                return False
        except UserProfile.DoesNotExist:
            self.stdout.write(
                self.style.WARNING(f'  ⚠ Profile not found for user: {cnic_verification.user.username}')
            )
            return False


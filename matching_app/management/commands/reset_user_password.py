"""
Django management command to reset a user's password.
Usage: python manage.py reset_user_password --email user@example.com --new-password newpass123
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Resets a user\'s password directly'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            required=True,
            help='Email of the user to reset password for',
        )
        parser.add_argument(
            '--new-password',
            type=str,
            required=True,
            help='New password to set',
        )

    def handle(self, *args, **options):
        email = options['email']
        new_password = options['new_password']
        
        # Find user by email
        user = User.objects.filter(email__iexact=email).first()
        
        if not user:
            self.stdout.write(
                self.style.ERROR(f'❌ User with email "{email}" not found!')
            )
            return
        
        # Set new password
        user.set_password(new_password)
        user.save(update_fields=['password'])
        
        self.stdout.write(
            self.style.SUCCESS(f'✅ Password reset successfully for {user.username} ({user.email})')
        )
        self.stdout.write(f'   New password: {new_password}')
        self.stdout.write('\nYou can now login with this password!')


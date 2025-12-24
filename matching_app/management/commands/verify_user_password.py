"""
Django management command to verify a user's password.
Usage: python manage.py verify_user_password --email user@example.com --password testpass
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Verifies if a user exists and if the password is correct'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            required=True,
            help='Email of the user to verify',
        )
        parser.add_argument(
            '--password',
            type=str,
            required=True,
            help='Password to check',
        )

    def handle(self, *args, **options):
        email = options['email']
        password = options['password']
        
        # Find user by email
        user = User.objects.filter(email__iexact=email).first()
        
        if not user:
            self.stdout.write(
                self.style.ERROR(f'❌ User with email "{email}" not found!')
            )
            self.stdout.write('\nAvailable users:')
            for u in User.objects.all()[:10]:
                self.stdout.write(f'  - {u.email} (username: {u.username}, active: {u.is_active})')
            return
        
        self.stdout.write(
            self.style.SUCCESS(f'✅ User found: {user.username} ({user.email})')
        )
        self.stdout.write(f'   User ID: {user.id}')
        self.stdout.write(f'   Is Active: {user.is_active}')
        self.stdout.write(f'   Date Joined: {user.date_joined}')
        
        # Check password
        password_correct = user.check_password(password)
        if password_correct:
            self.stdout.write(
                self.style.SUCCESS(f'✅ Password is CORRECT!')
            )
        else:
            self.stdout.write(
                self.style.ERROR(f'❌ Password is INCORRECT!')
            )
            self.stdout.write('\nTrying with trimmed password...')
            password_trimmed = password.strip()
            if password_trimmed != password:
                if user.check_password(password_trimmed):
                    self.stdout.write(
                        self.style.WARNING(f'⚠️  Password works when TRIMMED (had whitespace)')
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(f'❌ Password still incorrect even when trimmed')
                    )


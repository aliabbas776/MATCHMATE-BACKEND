"""
Django management command to create a test user matching preferences.
Usage: python manage.py create_test_user
"""
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from matching_app.models import UserProfile

User = get_user_model()


class Command(BaseCommand):
    help = 'Creates a test user profile matching the specified preferences'

    def add_arguments(self, parser):
        parser.add_argument(
            '--gender',
            type=str,
            default='female',
            choices=['male', 'female'],
            help='Gender of the test user (default: female)',
        )
        parser.add_argument(
            '--age',
            type=int,
            default=30,
            help='Age of the test user (default: 30)',
        )

    def handle(self, *args, **options):
        gender = options['gender']
        age = options['age']
        
        # Calculate date of birth based on age
        today = date.today()
        date_of_birth = today.replace(year=today.year - age)
        
        # Create user account
        username = f'test_user_{gender}_{age}'
        email = f'{username}@test.com'
        
        # Check if user already exists
        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(f'User {username} already exists. Updating profile...')
            )
            user = User.objects.get(username=username)
        else:
            user = User.objects.create_user(
                username=username,
                email=email,
                password='TestPass123!',
                first_name='Test',
                last_name='User',
            )
            self.stdout.write(
                self.style.SUCCESS(f'Created user: {username}')
            )
        
        # Create or update profile with matching preferences
        profile, created = UserProfile.objects.get_or_create(
            user=user,
            defaults={
                'candidate_name': f'Test {gender.capitalize()} User',
                'date_of_birth': date_of_birth,
                'gender': gender,
                'marital_status': 'Single',
                'religion': 'Muslim',
                'caste': 'Syed',
                'country': 'Pakistan',
                'city': 'Karachi',
                'phone_country_code': '+92',
                'phone_number': '1234567890',
                'has_disability': False,
                'is_public': True,
            }
        )
        
        if not created:
            # Update existing profile
            profile.candidate_name = f'Test {gender.capitalize()} User'
            profile.date_of_birth = date_of_birth
            profile.gender = gender
            profile.marital_status = 'Single'
            profile.religion = 'Muslim'
            profile.caste = 'Syed'
            profile.country = 'Pakistan'
            profile.city = 'Karachi'
            profile.has_disability = False
            profile.save()
            self.stdout.write(
                self.style.SUCCESS(f'Updated profile for user: {username}')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'Created profile for user: {username}')
            )
        
        # Display user info
        self.stdout.write(self.style.SUCCESS('\n=== Test User Created ==='))
        self.stdout.write(f'Username: {username}')
        self.stdout.write(f'Email: {email}')
        self.stdout.write(f'Password: TestPass123!')
        self.stdout.write(f'Gender: {gender}')
        self.stdout.write(f'Age: {age} (DOB: {date_of_birth})')
        self.stdout.write(f'Marital Status: Single')
        self.stdout.write(f'Religion: Muslim')
        self.stdout.write(f'Caste: Syed')
        self.stdout.write(f'Country: Pakistan')
        self.stdout.write(f'City: Karachi')
        self.stdout.write(f'Has Disability: False')
        self.stdout.write(self.style.SUCCESS('\nThis user will match your preferences!'))


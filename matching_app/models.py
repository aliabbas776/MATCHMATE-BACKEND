from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class LifeStatus(models.TextChoices):
    ALIVE = 'alive', 'Alive'
    DECEASED = 'deceased', 'Deceased'


class ProfileFor(models.TextChoices):
    MYSELF = 'Myself', 'Myself'
    BROTHER = 'Brother', 'Brother'
    SISTER = 'Sister', 'Sister'
    SON = 'Son', 'Son'
    DAUGHTER = 'Daughter', 'Daughter'
    OTHER = 'Other', 'Other'


class Gender(models.TextChoices):
    MALE = 'male', 'male'
    FEMALE = 'female', 'female'


class MaritalStatus(models.TextChoices):
    SINGLE = 'Single', 'Single'
    DIVORCED = 'Divorced', 'Divorced'
    MARRIED = 'Married', 'Married'
    SEPARATED = 'Separated', 'Separated'
    WIDOWER = 'Widower', 'Widower'


class Country(models.TextChoices):
    PAKISTAN = 'Pakistan', 'Pakistan'
    INDIA = 'India', 'India'
    USA = 'USA', 'USA'
    UK = 'UK', 'UK'
    CANADA = 'Canada', 'Canada'
    UAE = 'UAE', 'UAE'
    SAUDI_ARABIA = 'Saudi Arabia', 'Saudi Arabia'


class City(models.TextChoices):
    LAHORE = 'Lahore', 'Lahore'
    KARACHI = 'Karachi', 'Karachi'
    ISLAMABAD = 'Islamabad', 'Islamabad'
    FAISALABAD = 'Faisalabad', 'Faisalabad'
    MULTAN = 'Multan', 'Multan'
    RAWALPINDI = 'Rawalpindi', 'Rawalpindi'


class Religion(models.TextChoices):
    MUSLIM = 'Muslim', 'Muslim'
    CHRISTIAN = 'Christian', 'Christian'
    HINDU = 'Hindu', 'Hindu'
    SIKH = 'Sikh', 'Sikh'
    OTHER = 'Other', 'Other'


class Sect(models.TextChoices):
    SUNNI = 'Sunni', 'Sunni'
    SHIA = 'Shia', 'Shia'
    AHLE_HADITH = 'Ahle Hadith', 'Ahle Hadith'
    DEOBANDI = 'Deobandi', 'Deobandi'
    BARELVI = 'Barelvi', 'Barelvi'


class Caste(models.TextChoices):
    SYED = 'Syed', 'Syed'
    MUGHAL = 'Mughal', 'Mughal'
    RAJPUT = 'Rajput', 'Rajput'
    ARAIN = 'Arain', 'Arain'
    JATT = 'Jatt', 'Jatt'
    OTHER = 'Other', 'Other'


class EducationLevel(models.TextChoices):
    PRIMARY = 'Primary', 'Primary'
    SECONDARY = 'Secondary', 'Secondary'
    HIGHER_SECONDARY = 'Higher Secondary', 'Higher Secondary'
    BACHELOR = 'Bachelor', 'Bachelor'
    MASTER = 'Master', 'Master'
    PHD = 'PhD', 'PhD'
    DIPLOMA = 'Diploma', 'Diploma'


class EmploymentStatus(models.TextChoices):
    BUSINESS = 'Business', 'Business'
    EMPLOYED = 'Employed', 'Employed'
    HOMEMAKER = 'Home-maker', 'Home-maker'
    RETIRED = 'Retired', 'Retired'
    SELF_EMPLOYED = 'Self-employed', 'Self-employed'
    UNEMPLOYED = 'Unemployed', 'Unemployed'


class EmploymentStatusSimple(models.TextChoices):
    EMPLOYED = 'Employed', 'Employed'
    UNEMPLOYED = 'Unemployed', 'Unemployed'
    RETIRED = 'Retired', 'Retired'


class Profession(models.TextChoices):
    ENGINEER = 'Engineer', 'Engineer'
    DOCTOR = 'Doctor', 'Doctor'
    TEACHER = 'Teacher', 'Teacher'
    BUSINESS = 'Business', 'Business'
    IT_PROFESSIONAL = 'IT Professional', 'IT Professional'
    ACCOUNTANT = 'Accountant', 'Accountant'
    LAWYER = 'Lawyer', 'Lawyer'
    OTHER = 'Other', 'Other'


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    phone_country_code = models.CharField(max_length=5, default='+92', blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)
    is_public = models.BooleanField(default=True)
    candidate_name = models.CharField(max_length=255, blank=True)
    hidden_name = models.BooleanField(default=False)
    date_of_birth = models.DateField(blank=True, null=True)
    country = models.CharField(max_length=100, choices=Country.choices, blank=True)
    city = models.CharField(max_length=100, choices=City.choices, blank=True)
    religion = models.CharField(max_length=100, choices=Religion.choices, blank=True)
    sect = models.CharField(max_length=100, choices=Sect.choices, blank=True)
    caste = models.CharField(max_length=100, choices=Caste.choices, blank=True)
    height_cm = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    weight_kg = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    profile_for = models.CharField(max_length=20, choices=ProfileFor.choices, blank=True)
    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True)
    marital_status = models.CharField(max_length=15, choices=MaritalStatus.choices, blank=True)
    education_level = models.CharField(max_length=120, choices=EducationLevel.choices, blank=True)
    employment_status = models.CharField(
        max_length=30,
        choices=EmploymentStatus.choices,
        blank=True,
    )
    profession = models.CharField(max_length=120, choices=Profession.choices, blank=True)
    father_status = models.CharField(max_length=10, choices=LifeStatus.choices, blank=True)
    father_employment_status = models.CharField(max_length=30, choices=EmploymentStatusSimple.choices, blank=True)
    mother_status = models.CharField(max_length=10, choices=LifeStatus.choices, blank=True)
    mother_employment_status = models.CharField(max_length=30, choices=EmploymentStatusSimple.choices, blank=True)
    total_brothers = models.PositiveIntegerField(default=0)
    total_sisters = models.PositiveIntegerField(default=0)
    blur_photo = models.BooleanField(default=False)
    has_disability = models.BooleanField(default=False)
    generated_description = models.TextField(blank=True, null=True)

    #CNIC Verification
    cnic_number = models.CharField(max_length=15, blank=True)
    cnic_verification_status = models.CharField(
        max_length=20,
        choices=[
            ('unverified', 'Unverified'),
            ('pending', 'Pending'),
            ('verified', 'Verified'),
            ('rejected', 'Rejected'),
        ],
        default='unverified',
    )
    cnic_verified_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_completed(self) -> bool:
        """
        Return True when the user has filled the minimum fields required for matching.
        """
        required_fields = ['candidate_name', 'gender', 'city', 'caste', 'religion']
        return all(bool(getattr(self, field)) for field in required_fields)

    def __str__(self):
        return f"{self.user.username}'s profile"


class PasswordResetOTP(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='password_reset_otps',
    )
    code = models.CharField(max_length=4, unique=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def is_expired(self):
        return timezone.now() >= self.expires_at

    def __str__(self):
        return f'OTP for {self.user.email} ({self.code})'


class MatchPreference(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='match_preference',
    )
    status = models.CharField(
        max_length=15,
        choices=MaritalStatus.choices,
        blank=True,
    )
    religion = models.CharField(max_length=100, choices=Religion.choices, blank=True)
    caste = models.CharField(max_length=100, choices=Caste.choices, blank=True)
    country = models.CharField(max_length=100, choices=Country.choices, blank=True)
    city = models.CharField(max_length=100, choices=City.choices, blank=True)
    employment_status = models.CharField(
        max_length=30,
        choices=EmploymentStatus.choices,
        blank=True,
    )
    profession = models.CharField(max_length=120, choices=Profession.choices, blank=True)
    prefers_disability = models.BooleanField(
        null=True,
        blank=True,
        help_text='Set to true to include only users with a disability, false to exclude them, leave blank for any.',
    )
    min_age = models.PositiveIntegerField(null=True, blank=True)
    max_age = models.PositiveIntegerField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if self.min_age and self.max_age and self.min_age > self.max_age:
            raise ValidationError('Minimum age cannot exceed maximum age.')

    def save(self, *args, **kwargs):
        self.full_clean(exclude=None)
        return super().save(*args, **kwargs)

    def __str__(self):
        return f'MatchPreference<{self.user_id}>'


class CNICVerification(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        VERIFIED = 'verified', 'Verified'
        REJECTED = 'rejected', 'Rejected'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cnic_verification',
    )
    front_image = models.ImageField(upload_to='cnic/front/')
    back_image = models.ImageField(upload_to='cnic/back/')
    extracted_full_name = models.CharField(max_length=255, blank=True)
    extracted_cnic = models.CharField(max_length=20, blank=True)
    extracted_dob = models.DateField(blank=True, null=True)
    extracted_gender = models.CharField(max_length=10, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    rejection_reason = models.TextField(blank=True)
    blur_score = models.FloatField(blank=True, null=True)
    tampering_detected = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'CNICVerification<{self.user_id}> {self.status}'


class UserConnection(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        BLOCKED = 'blocked', 'Blocked'

    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='connections_sent',
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='connections_received',
    )
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['from_user', 'to_user'],
                name='unique_connection_request',
            ),
            models.CheckConstraint(
                check=~Q(from_user=F('to_user')),
                name='prevent_self_connection',
            ),
        ]
        ordering = ['-updated_at']

    def __str__(self):
        return f'Connection<{self.from_user_id}->{self.to_user_id}> {self.status}'

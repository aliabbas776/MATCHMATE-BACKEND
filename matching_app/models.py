from django.conf import settings
from django.db import models
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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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

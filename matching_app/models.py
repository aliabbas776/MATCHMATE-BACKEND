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
    KARACHI = 'Karachi', 'Karachi'
    LAHORE = 'Lahore', 'Lahore'
    ISLAMABAD = 'Islamabad', 'Islamabad'
    RAWALPINDI = 'Rawalpindi', 'Rawalpindi'
    FAISALABAD = 'Faisalabad', 'Faisalabad'
    MULTAN = 'Multan', 'Multan'
    GUJRANWALA = 'Gujranwala', 'Gujranwala'
    SIALKOT = 'Sialkot', 'Sialkot'
    GUJRAT = 'Gujrat', 'Gujrat'
    SHEIKHUPURA = 'Sheikhupura', 'Sheikhupura'
    SARGODHA = 'Sargodha', 'Sargodha'
    BAHAWALPUR = 'Bahawalpur', 'Bahawalpur'
    RAHIM_YAR_KHAN = 'Rahim Yar Khan', 'Rahim Yar Khan'
    DERA_GHAZI_KHAN = 'Dera Ghazi Khan', 'Dera Ghazi Khan'
    SAHIWAL = 'Sahiwal', 'Sahiwal'
    OKARA = 'Okara', 'Okara'
    KASUR = 'Kasur', 'Kasur'
    JHANG = 'Jhang', 'Jhang'

    HYDERABAD = 'Hyderabad', 'Hyderabad'
    SUKKUR = 'Sukkur', 'Sukkur'
    LARKANA = 'Larkana', 'Larkana'
    NAWABSHAH = 'Nawabshah', 'Nawabshah'
    MIRPUR_KHAS = 'Mirpur Khas', 'Mirpur Khas'
    THATTA = 'Thatta', 'Thatta'
    JACOBABAD = 'Jacobabad', 'Jacobabad'

    PESHAWAR = 'Peshawar', 'Peshawar'
    MARDAN = 'Mardan', 'Mardan'
    SWABI = 'Swabi', 'Swabi'
    ABBOTTABAD = 'Abbottabad', 'Abbottabad'
    MANSEHRA = 'Mansehra', 'Mansehra'
    HARIPUR = 'Haripur', 'Haripur'
    KOHAT = 'Kohat', 'Kohat'
    DERA_ISMAIL_KHAN = 'Dera Ismail Khan', 'Dera Ismail Khan'
    NOWSHERA = 'Nowshera', 'Nowshera'

    QUETTA = 'Quetta', 'Quetta'
    GWADAR = 'Gwadar', 'Gwadar'
    TURBAT = 'Turbat', 'Turbat'
    KHUZDAR = 'Khuzdar', 'Khuzdar'
    ZHOB = 'Zhob', 'Zhob'
    CHAMAN = 'Chaman', 'Chaman'
    MASTUNG = 'Mastung', 'Mastung'

    MUZAFFARABAD = 'Muzaffarabad', 'Muzaffarabad'
    MIRPUR_AJK = 'Mirpur (AJK)', 'Mirpur (AJK)'
    KOTLI = 'Kotli', 'Kotli'

    GILGIT = 'Gilgit', 'Gilgit'
    SKARDU = 'Skardu', 'Skardu'
    HUNZA = 'Hunza', 'Hunza'

    OTHER = 'Other', 'Other'


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
    ARAIN = 'Arain', 'Arain'
    JATT = 'Jatt', 'Jatt'
    RAJPUT = 'Rajput', 'Rajput'
    GUJJAR = 'Gujjar', 'Gujjar'
    SHEIKH = 'Sheikh', 'Sheikh'
    SYED = 'Syed', 'Syed'
    MALIK = 'Malik', 'Malik'
    AWAN = 'Awan', 'Awan'
    BHATTI = 'Bhatti', 'Bhatti'
    CHAUDHRY = 'Chaudhry', 'Chaudhry'
    WARRAICH = 'Warraich', 'Warraich'
    GONDAL = 'Gondal', 'Gondal'
    KHARAL = 'Kharal', 'Kharal'
    SANDHU = 'Sandhu', 'Sandhu'
    CHEEMA = 'Cheema', 'Cheema'
    BAJWA = 'Bajwa', 'Bajwa'
    VIRK = 'Virk', 'Virk'
    GILL = 'Gill', 'Gill'
    MINHAS = 'Minhas', 'Minhas'
    JANJUA = 'Janjua', 'Janjua'
    NIAZI = 'Niazi', 'Niazi'
    QURESHI = 'Qureshi', 'Qureshi'
    ANSARI = 'Ansari', 'Ansari'
    FAROOQI = 'Farooqi', 'Farooqi'
    SIDDIQUI = 'Siddiqui', 'Siddiqui'
    ABBASI = 'Abbasi', 'Abbasi'
    BHUTTO = 'Bhutto', 'Bhutto'
    SHAH = 'Shah', 'Shah'
    SOOMRO = 'Soomro', 'Soomro'
    SAMMA = 'Samma', 'Samma'
    MAHAR = 'Mahar', 'Mahar'
    JUNEJO = 'Junejo', 'Junejo'
    PANHWAR = 'Panhwar', 'Panhwar'
    KALHORO = 'Kalhoro', 'Kalhoro'
    CHANDIO = 'Chandio', 'Chandio'
    BROHI = 'Brohi', 'Brohi'
    SOLANGI = 'Solangi', 'Solangi'
    MANGRIO = 'Mangrio', 'Mangrio'
    LASHARI = 'Lashari', 'Lashari'
    RIND = 'Rind', 'Rind'
    TALPUR = 'Talpur', 'Talpur'
    KHOSO = 'Khoso', 'Khoso'
    MIRANI = 'Mirani', 'Mirani'
    BUGTI = 'Bugti', 'Bugti'
    MARRI = 'Marri', 'Marri'
    MENGAL = 'Mengal', 'Mengal'
    JAMALI = 'Jamali', 'Jamali'
    LEGHARI = 'Leghari', 'Leghari'
    RAISANI = 'Raisani', 'Raisani'
    KHOSA = 'Khosa', 'Khosa'
    AFRIDI = 'Afridi', 'Afridi'
    YOUSAFZAI = 'Yousafzai', 'Yousafzai'
    KHATTAK = 'Khattak', 'Khattak'
    BANGASH = 'Bangash', 'Bangash'
    SHINWARI = 'Shinwari', 'Shinwari'
    ORAKZAI = 'Orakzai', 'Orakzai'
    MOHMAND = 'Mohmand', 'Mohmand'
    WAZIR = 'Wazir', 'Wazir'
    MEHSUD = 'Mehsud', 'Mehsud'
    TURI = 'Turi', 'Turi'
    KAKAR = 'Kakar', 'Kakar'
    ACHAKZAI = 'Achakzai', 'Achakzai'
    POPALZAI = 'Popalzai', 'Popalzai'
    BARAKZAI = 'Barakzai', 'Barakzai'
    BUTT = 'Butt', 'Butt'
    DAR = 'Dar', 'Dar'
    MIR = 'Mir', 'Mir'
    BHAT = 'Bhat', 'Bhat'
    LONE = 'Lone', 'Lone'
    WANI = 'Wani', 'Wani'
    MAZARI = 'Mazari', 'Mazari'
    GORCHANI = 'Gorchani', 'Gorchani'
    QAISRANI = 'Qaisrani', 'Qaisrani'
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
    birth_country = models.CharField(max_length=100, blank=True, help_text='Country where the user was born')
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
    # Education Details
    institute_name = models.CharField(max_length=255, blank=True, help_text='Name of the educational institute')
    degree_title = models.CharField(max_length=255, blank=True, help_text='Title of the degree obtained')
    duration = models.CharField(max_length=100, blank=True, help_text='Duration of education (e.g., "2018-2022" or "4 years")')
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
    
    # Admin Verification
    admin_verification_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('verified', 'Verified'),
            ('rejected', 'Rejected'),
        ],
        default='pending',
        help_text='Admin verification status. Profile shows 95% until admin verifies, then 100%.'
    )
    admin_verified_at = models.DateTimeField(blank=True, null=True)
    
    # Profile status
    is_disabled = models.BooleanField(
        default=False,
        help_text='Profile is disabled due to multiple reports. Requires admin approval to re-enable.'
    )
    disabled_at = models.DateTimeField(blank=True, null=True)
    disabled_reason = models.TextField(blank=True, help_text='Reason for profile being disabled')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_completed(self) -> bool:
        """
        Return True when the user has filled the minimum fields required for matching.
        """
        required_fields = ['candidate_name', 'gender', 'city', 'caste', 'religion']
        return all(bool(getattr(self, field)) for field in required_fields)

    def get_completion_percentage(self) -> dict:
        """
        Calculate profile completion percentage based on filled fields.
        Returns a dictionary with percentage and breakdown by section.
        """
        # Define fields with their weights (importance)
        # Total weight = 100
        field_weights = {
            # Candidate Information (30%)
            'candidate_name': 5,
            'date_of_birth': 5,
            'country': 3,
            'city': 3,
            'religion': 3,
            'sect': 2,
            'caste': 3,
            'height_cm': 2,
            'weight_kg': 2,
            'phone_number': 2,
            
            # Profile Details (15%)
            'profile_for': 3,
            'gender': 5,
            'marital_status': 7,
            
            # Family Details (15%)
            'father_status': 4,
            'father_employment_status': 3,
            'mother_status': 4,
            'mother_employment_status': 3,
            'total_brothers': 0.5,
            'total_sisters': 0.5,
            
            # Education & Employment (20%)
            'education_level': 7,
            'employment_status': 7,
            'profession': 6,
            
            # Media (15%)
            'profile_picture': 15,
            
            # Admin Verification (5%) - Only counts if verified
            'admin_verification_status': 5,
        }
        
        completed_weight = 0
        total_weight = sum(field_weights.values())
        section_breakdown = {
            'candidate_information': {'completed': 0, 'total': 0},
            'profile_details': {'completed': 0, 'total': 0},
            'family_details': {'completed': 0, 'total': 0},
            'education_employment': {'completed': 0, 'total': 0},
            'media': {'completed': 0, 'total': 0},
            'admin_verification': {'completed': 0, 'total': 0},
        }
        
        # Section mapping
        section_map = {
            'candidate_name': 'candidate_information',
            'date_of_birth': 'candidate_information',
            'country': 'candidate_information',
            'city': 'candidate_information',
            'religion': 'candidate_information',
            'sect': 'candidate_information',
            'caste': 'candidate_information',
            'height_cm': 'candidate_information',
            'weight_kg': 'candidate_information',
            'phone_number': 'candidate_information',
            'profile_for': 'profile_details',
            'gender': 'profile_details',
            'marital_status': 'profile_details',
            'father_status': 'family_details',
            'father_employment_status': 'family_details',
            'mother_status': 'family_details',
            'mother_employment_status': 'family_details',
            'total_brothers': 'family_details',
            'total_sisters': 'family_details',
            'education_level': 'education_employment',
            'employment_status': 'education_employment',
            'profession': 'education_employment',
            'profile_picture': 'media',
            'admin_verification_status': 'admin_verification',
        }
        
        # Check each field
        for field, weight in field_weights.items():
            section = section_map.get(field, 'additional_info')
            section_breakdown[section]['total'] += weight
            
            value = getattr(self, field, None)
            is_filled = False
            
            if field == 'admin_verification_status':
                # Special case: only count if admin verified
                is_filled = value == 'verified'
            elif field == 'total_brothers' or field == 'total_sisters':
                # These are integers, 0 is a valid value
                is_filled = value is not None
            elif isinstance(value, bool):
                # Boolean fields are always filled
                is_filled = True
            else:
                # Check if field has a non-empty value
                is_filled = bool(value) and str(value).strip() != ''
            
            if is_filled:
                completed_weight += weight
                section_breakdown[section]['completed'] += weight
        
        percentage = round((completed_weight / total_weight) * 100, 2)
        
        # Calculate section percentages
        section_percentages = {}
        for section, data in section_breakdown.items():
            if data['total'] > 0:
                section_percentages[section] = round((data['completed'] / data['total']) * 100, 2)
            else:
                section_percentages[section] = 0.0
        
        return {
            'completion_percentage': percentage,
            'completed_fields': completed_weight,
            'total_fields': total_weight,
            'sections': section_percentages,
            'is_completed': self.is_completed,
        }

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


class UserProfileImage(models.Model):
    """
    Model to store multiple images for a user profile.
    """
    profile = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name='images',
        help_text='Profile that owns this image',
    )
    image = models.ImageField(
        upload_to='profiles/images/',
        help_text='Profile image file',
    )
    order = models.PositiveIntegerField(
        default=0,
        help_text='Order/position of image (for sorting)',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'created_at']
        verbose_name = 'Profile Image'
        verbose_name_plural = 'Profile Images'

    def __str__(self):
        return f'Image {self.id} for {self.profile.user.username}'


class UserConnection(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

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
                condition=~Q(from_user=F('to_user')),
                name='prevent_self_connection',
            ),
        ]
        ordering = ['-updated_at']

    def __str__(self):
        return f'Connection<{self.from_user_id}->{self.to_user_id}> {self.status}'


class Message(models.Model):
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='messages_sent',
    )
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='messages_received',
    )
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['sender', 'receiver', '-created_at']),
            models.Index(fields=['receiver', 'is_read', '-created_at']),
        ]

    def __str__(self):
        return f'Message<{self.sender_id}->{self.receiver_id}> {self.created_at}'


class Session(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ACTIVE = 'active', 'Active'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    initiator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sessions_initiated',
    )
    participant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sessions_participated',
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    
    # Zoom meeting details
    zoom_meeting_id = models.CharField(max_length=255, blank=True, null=True)
    zoom_meeting_url = models.URLField(blank=True, null=True)
    zoom_meeting_password = models.CharField(max_length=100, blank=True, null=True)
    
    # Track who started the session (generated the Zoom link)
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='sessions_started',
        null=True,
        blank=True,
        help_text='User who generated the Zoom link',
    )
    
    # Ready status tracking
    initiator_ready = models.BooleanField(default=False)
    participant_ready = models.BooleanField(default=False)
    
    # Timestamps
    started_at = models.DateTimeField(blank=True, null=True)
    ended_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['initiator', 'status', '-created_at']),
            models.Index(fields=['participant', 'status', '-created_at']),
            models.Index(fields=['status', '-created_at']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~Q(initiator=F('participant')),
                name='prevent_self_session',
            ),
        ]

    def __str__(self):
        return f'Session<{self.initiator_id}->{self.participant_id}> {self.status}'

    def can_join(self, user):
        """Check if a user can join the session.
        
        The user who generated the Zoom link cannot enter until the other
        participant marks ready. The other participant can join once they mark ready.
        """
        if self.status != self.Status.ACTIVE:
            return False
        if user not in [self.initiator, self.participant]:
            return False
        
        # If no one has started yet, no one can join
        if not self.started_by:
            return False
        
        # The user who started the session can only join if the other participant is ready
        if user == self.started_by:
            # Check if the other participant is ready
            if user == self.initiator:
                return self.participant_ready
            else:  # user == self.participant
                return self.initiator_ready
        
        # The other participant (who didn't start) can join once they mark ready
        if user == self.initiator:
            return self.initiator_ready
        if user == self.participant:
            return self.participant_ready
        
        return False

    def mark_ready(self, user):
        """Mark a user as ready to join."""
        if user == self.initiator:
            self.initiator_ready = True
        elif user == self.participant:
            self.participant_ready = True
        else:
            raise ValueError("User is not a participant in this session")
        self.save(update_fields=['initiator_ready', 'participant_ready', 'updated_at'])


class SessionJoinToken(models.Model):
    """One-time tokenized join links for secure session access."""
    session = models.ForeignKey(
        Session,
        on_delete=models.CASCADE,
        related_name='join_tokens',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='session_join_tokens',
    )
    token = models.CharField(max_length=64, unique=True, db_index=True)
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['token', 'is_used']),
            models.Index(fields=['session', 'user', 'is_used']),
        ]

    def __str__(self):
        return f'JoinToken<Session:{self.session_id}, User:{self.user_id}>'

    def is_expired(self):
        return timezone.now() >= self.expires_at

    def is_valid(self):
        return not self.is_used and not self.is_expired()


class SessionAuditLog(models.Model):
    """Audit log for all session events and state changes."""
    class EventType(models.TextChoices):
        CREATED = 'created', 'Session Created'
        STARTED = 'started', 'Session Started'
        READY = 'ready', 'Participant Ready'
        JOINED = 'joined', 'Participant Joined'
        LEFT = 'left', 'Participant Left'
        ENDED = 'ended', 'Session Ended'
        CANCELLED = 'cancelled', 'Session Cancelled'
        ZOOM_LINK_GENERATED = 'zoom_link_generated', 'Zoom Link Generated'

    session = models.ForeignKey(
        Session,
        on_delete=models.CASCADE,
        related_name='audit_logs',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='session_audit_logs',
        null=True,
        blank=True,
    )
    event_type = models.CharField(max_length=50, choices=EventType.choices)
    message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['session', '-created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['event_type', '-created_at']),
        ]

    def __str__(self):
        return f'AuditLog<Session:{self.session_id}, {self.event_type}>'


class UserReport(models.Model):
    """
    Model to track reports made by users against other users.
    """
    class ReportReason(models.TextChoices):
        INAPPROPRIATE_CONTENT = 'inappropriate_content', 'Inappropriate Content'
        FAKE_PROFILE = 'fake_profile', 'Fake Profile'
        HARASSMENT = 'harassment', 'Harassment'
        SPAM = 'spam', 'Spam'
        SCAM = 'scam', 'Scam'
        OTHER = 'other', 'Other'

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reports_made',
        help_text='User who made the report',
    )
    reported_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reports_received',
        help_text='User who is being reported',
    )
    reason = models.CharField(
        max_length=50,
        blank=True,
        help_text='Reason for reporting the user',
    )
    description = models.TextField(
        blank=True,
        help_text='Additional details about the report',
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending Review'),
            ('reviewed', 'Reviewed'),
            ('dismissed', 'Dismissed'),
        ],
        default='pending',
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reports_reviewed',
        help_text='Admin who reviewed this report',
    )
    reviewed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['reported_user', 'status', '-created_at']),
            models.Index(fields=['reporter', '-created_at']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~Q(reporter=F('reported_user')),
                name='prevent_self_report',
            ),
        ]

    def __str__(self):
        return f'Report<{self.reporter_id}->{self.reported_user_id}> {self.reason}'


class SubscriptionPlan(models.Model):
    """
    Model to define subscription plan tiers.
    """
    class PlanTier(models.TextChoices):
        FREE = 'free', 'Free'
        SILVER = 'silver', 'Silver'
        GOLD = 'gold', 'Gold'
        PLATINUM = 'platinum', 'Platinum'

    tier = models.CharField(
        max_length=20,
        choices=PlanTier.choices,
        unique=True,
        help_text='Subscription tier level',
    )
    name = models.CharField(
        max_length=100,
        help_text='Display name for the subscription plan',
    )
    description = models.TextField(
        blank=True,
        help_text='Description of what this plan includes',
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text='Monthly price (0.00 for free tier)',
    )
    duration_days = models.IntegerField(
        default=30,
        help_text='Duration of subscription in days',
    )
    is_active = models.BooleanField(
        default=True,
        help_text='Whether this plan is currently available for subscription',
    )
    
    # Features/benefits for each tier
    max_profile_views = models.IntegerField(
        default=-1,
        help_text='Maximum profile views per month (-1 for unlimited)',
    )
    max_connections = models.IntegerField(
        default=-1,
        help_text='Maximum connections per month (-1 for unlimited)',
    )
    max_connection_requests = models.IntegerField(
        default=-1,
        help_text='Maximum connection requests per month (-1 for unlimited)',
    )
    max_chat_users = models.IntegerField(
        default=-1,
        help_text='Maximum number of different users you can chat with (-1 for unlimited)',
    )
    max_sessions = models.IntegerField(
        default=-1,
        help_text='Maximum number of call sessions per month (-1 for unlimited)',
    )
    can_send_messages = models.BooleanField(
        default=True,
        help_text='Can send messages to connections',
    )
    can_view_photos = models.BooleanField(
        default=True,
        help_text='Can view profile photos',
    )
    can_see_who_viewed = models.BooleanField(
        default=False,
        help_text='Can see who viewed their profile',
    )
    priority_support = models.BooleanField(
        default=False,
        help_text='Priority customer support',
    )
    advanced_search = models.BooleanField(
        default=False,
        help_text='Access to advanced search filters',
    )
    verified_badge = models.BooleanField(
        default=False,
        help_text='Verified badge on profile',
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['price']
        verbose_name = 'Subscription Plan'
        verbose_name_plural = 'Subscription Plans'

    def __str__(self):
        return f'{self.name} ({self.tier})'


class UserSubscription(models.Model):
    """
    Model to track user subscriptions.
    """
    class SubscriptionStatus(models.TextChoices):
        ACTIVE = 'active', 'Active'
        EXPIRED = 'expired', 'Expired'
        CANCELLED = 'cancelled', 'Cancelled'
        PENDING = 'pending', 'Pending'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='subscription',
        help_text='User who has this subscription',
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name='user_subscriptions',
        help_text='Subscription plan',
    )
    status = models.CharField(
        max_length=20,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.ACTIVE,
        help_text='Current subscription status',
    )
    started_at = models.DateTimeField(
        auto_now_add=True,
        help_text='When the subscription started',
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When the subscription expires (null for lifetime/free)',
    )
    auto_renew = models.BooleanField(
        default=False,
        help_text='Whether subscription auto-renews',
    )
    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When the subscription was cancelled',
    )
    cancellation_reason = models.TextField(
        blank=True,
        help_text='Reason for cancellation',
    )
    
    # Usage tracking
    profile_views_used = models.IntegerField(
        default=0,
        help_text='Number of profile views used in current period',
    )
    connections_used = models.IntegerField(
        default=0,
        help_text='Number of connections used in current period',
    )
    connection_requests_used = models.IntegerField(
        default=0,
        help_text='Number of connection requests sent in current period',
    )
    chat_users_count = models.IntegerField(
        default=0,
        help_text='Number of different users user has chatted with',
    )
    sessions_used = models.IntegerField(
        default=0,
        help_text='Number of call sessions created in current period',
    )
    last_reset_at = models.DateTimeField(
        auto_now_add=True,
        help_text='When usage counters were last reset',
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'User Subscription'
        verbose_name_plural = 'User Subscriptions'
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'expires_at']),
        ]

    def __str__(self):
        return f'{self.user.username} - {self.plan.name} ({self.status})'

    @property
    def is_active(self):
        """Check if subscription is currently active."""
        if self.status != self.SubscriptionStatus.ACTIVE:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True

    @property
    def days_remaining(self):
        """Get number of days remaining in subscription."""
        if not self.expires_at:
            return None  # Lifetime/free subscription
        if not self.is_active:
            return 0
        delta = self.expires_at - timezone.now()
        return max(0, delta.days)

    def can_view_profile(self):
        """Check if user can view another profile based on plan limits."""
        if self.plan.max_profile_views == -1:
            return True  # Unlimited
        return self.profile_views_used < self.plan.max_profile_views

    def can_make_connection(self):
        """Check if user can make a new connection based on plan limits."""
        if self.plan.max_connections == -1:
            return True  # Unlimited
        return self.connections_used < self.plan.max_connections

    def can_send_connection_request(self):
        """Check if user can send a new connection request based on plan limits."""
        if self.plan.max_connection_requests == -1:
            return True  # Unlimited
        return self.connection_requests_used < self.plan.max_connection_requests

    def can_chat_with_user(self, target_user):
        """Check if user can chat with a specific user based on plan limits."""
        if self.plan.max_chat_users == -1:
            return True  # Unlimited
        
        # Check if user has already chatted with this user (in either direction)
        # If they've chatted before, always allow (no limit check needed)
        from .models import Message
        has_chatted = Message.objects.filter(
            Q(sender=self.user, receiver=target_user) |
            Q(sender=target_user, receiver=self.user)
        ).exists()
        
        if has_chatted:
            return True  # Already chatting with this user, allow continuation
        
        # This is a new chat - check if user has reached their limit
        # Count distinct users user has chatted with (combining sent and received)
        # Get all unique user IDs user has chatted with
        sent_to_users = set(
            Message.objects.filter(sender=self.user)
            .values_list('receiver_id', flat=True)
            .distinct()
        )
        received_from_users = set(
            Message.objects.filter(receiver=self.user)
            .values_list('sender_id', flat=True)
            .distinct()
        )
        
        # Combine both sets to get total distinct chat partners
        total_distinct_chat_users = len(sent_to_users | received_from_users)
        
        # User can chat if current count is less than the limit
        # e.g., if limit is 1 and count is 0, they can chat (0 < 1 = True)
        # if limit is 1 and count is 1, they cannot chat (1 < 1 = False)
        return total_distinct_chat_users < self.plan.max_chat_users

    def can_create_session(self):
        """Check if user can create a new call session based on plan limits."""
        if self.plan.max_sessions == -1:
            return True  # Unlimited
        return self.sessions_used < self.plan.max_sessions

    def reset_usage(self):
        """Reset usage counters (called monthly)."""
        self.profile_views_used = 0
        self.connections_used = 0
        self.connection_requests_used = 0
        self.sessions_used = 0
        # Reset chat_users_count to allow fresh quota for new month
        # The count will be recalculated dynamically when needed
        self.chat_users_count = 0
        self.last_reset_at = timezone.now()
        self.save(update_fields=[
            'profile_views_used',
            'connections_used',
            'connection_requests_used',
            'sessions_used',
            'chat_users_count',
            'last_reset_at'
        ])


class Device(models.Model):
    """
    Model to store FCM device tokens for push notifications.
    Supports multiple devices per user (e.g., phone, tablet).
    """
    class DeviceType(models.TextChoices):
        ANDROID = 'android', 'Android'
        IOS = 'ios', 'iOS'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='devices',
        help_text='User who owns this device',
    )
    fcm_token = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text='Firebase Cloud Messaging token for this device',
    )
    device_type = models.CharField(
        max_length=10,
        choices=DeviceType.choices,
        help_text='Type of device (Android or iOS)',
    )
    is_active = models.BooleanField(
        default=True,
        help_text='Whether this device token is currently active',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['fcm_token', 'is_active']),
        ]
        verbose_name = 'Device'
        verbose_name_plural = 'Devices'

    def __str__(self):
        return f'Device<{self.user.username}, {self.device_type}, {self.fcm_token[:20]}...>'


from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('matching_app', '0006_userprofile_generated_description'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='has_disability',
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name='MatchPreference',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(blank=True, choices=[('Single', 'Single'), ('Divorced', 'Divorced'), ('Married', 'Married'), ('Separated', 'Separated'), ('Widower', 'Widower')], max_length=15)),
                ('religion', models.CharField(blank=True, choices=[('Muslim', 'Muslim'), ('Christian', 'Christian'), ('Hindu', 'Hindu'), ('Sikh', 'Sikh'), ('Other', 'Other')], max_length=100)),
                ('caste', models.CharField(blank=True, choices=[('Syed', 'Syed'), ('Mughal', 'Mughal'), ('Rajput', 'Rajput'), ('Arain', 'Arain'), ('Jatt', 'Jatt'), ('Other', 'Other')], max_length=100)),
                ('country', models.CharField(blank=True, choices=[('Pakistan', 'Pakistan'), ('India', 'India'), ('USA', 'USA'), ('UK', 'UK'), ('Canada', 'Canada'), ('UAE', 'UAE'), ('Saudi Arabia', 'Saudi Arabia')], max_length=100)),
                ('city', models.CharField(blank=True, choices=[('Lahore', 'Lahore'), ('Karachi', 'Karachi'), ('Islamabad', 'Islamabad'), ('Faisalabad', 'Faisalabad'), ('Multan', 'Multan'), ('Rawalpindi', 'Rawalpindi')], max_length=100)),
                ('employment_status', models.CharField(blank=True, choices=[('Business', 'Business'), ('Employed', 'Employed'), ('Home-maker', 'Home-maker'), ('Retired', 'Retired'), ('Self-employed', 'Self-employed'), ('Unemployed', 'Unemployed')], max_length=30)),
                ('profession', models.CharField(blank=True, choices=[('Engineer', 'Engineer'), ('Doctor', 'Doctor'), ('Teacher', 'Teacher'), ('Business', 'Business'), ('IT Professional', 'IT Professional'), ('Accountant', 'Accountant'), ('Lawyer', 'Lawyer'), ('Other', 'Other')], max_length=120)),
                ('prefers_disability', models.BooleanField(blank=True, help_text='Set to true to include only users with a disability, false to exclude them, leave blank for any.', null=True)),
                ('min_age', models.PositiveIntegerField(blank=True, null=True)),
                ('max_age', models.PositiveIntegerField(blank=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=models.deletion.CASCADE, related_name='match_preference', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]



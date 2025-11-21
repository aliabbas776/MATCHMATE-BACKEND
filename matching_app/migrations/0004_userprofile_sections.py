from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('matching_app', '0003_alter_passwordresetotp_code'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='blur_photo',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='candidate_name',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='caste',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='city',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='country',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='date_of_birth',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='education_level',
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='employment_status',
            field=models.CharField(blank=True, choices=[('business', 'Business'), ('employed', 'Employed'), ('home-maker', 'Home-maker'), ('retired', 'Retired'), ('self-employed', 'Self-employed'), ('unemployed', 'Unemployed')], max_length=30),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='father_employment_status',
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='father_status',
            field=models.CharField(blank=True, choices=[('alive', 'Alive'), ('deceased', 'Deceased')], max_length=10),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='gender',
            field=models.CharField(blank=True, choices=[('male', 'Male'), ('female', 'Female')], max_length=10),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='height_cm',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='hidden_name',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='marital_status',
            field=models.CharField(blank=True, choices=[('single', 'Single'), ('divorced', 'Divorced'), ('married', 'Married'), ('separated', 'Separated'), ('widower', 'Widower')], max_length=15),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='mother_employment_status',
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='mother_status',
            field=models.CharField(blank=True, choices=[('alive', 'Alive'), ('deceased', 'Deceased')], max_length=10),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='phone_country_code',
            field=models.CharField(blank=True, default='+92', max_length=5),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='profession',
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='profile_for',
            field=models.CharField(blank=True, choices=[('myself', 'Myself'), ('brother', 'Brother'), ('sister', 'Sister'), ('son', 'Son'), ('daughter', 'Daughter'), ('other', 'Other')], max_length=20),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='religion',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='sect',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='total_brothers',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='total_sisters',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='weight_kg',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True),
        ),
        migrations.AlterField(
            model_name='userprofile',
            name='phone_number',
            field=models.CharField(blank=True, max_length=20),
        ),
    ]


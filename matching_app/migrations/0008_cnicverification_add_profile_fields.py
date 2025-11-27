from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('matching_app', '0007_matchpreference_has_disability'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='cnic_number',
            field=models.CharField(blank=True, max_length=15),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='cnic_verification_status',
            field=models.CharField(
                choices=[
                    ('unverified', 'Unverified'),
                    ('pending', 'Pending'),
                    ('verified', 'Verified'),
                    ('rejected', 'Rejected'),
                ],
                default='unverified',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='cnic_verified_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name='CNICVerification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('front_image', models.ImageField(upload_to='cnic/front/')),
                ('back_image', models.ImageField(upload_to='cnic/back/')),
                ('extracted_full_name', models.CharField(blank=True, max_length=255)),
                ('extracted_cnic', models.CharField(blank=True, max_length=20)),
                ('extracted_dob', models.DateField(blank=True, null=True)),
                ('extracted_gender', models.CharField(blank=True, max_length=10)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('verified', 'Verified'), ('rejected', 'Rejected')], default='pending', max_length=10)),
                ('rejection_reason', models.TextField(blank=True)),
                ('blur_score', models.FloatField(blank=True, null=True)),
                ('tampering_detected', models.BooleanField(default=False)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.OneToOneField(on_delete=models.deletion.CASCADE, related_name='cnic_verification', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]



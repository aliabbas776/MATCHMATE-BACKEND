from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('matching_app', '0009_userprofile_is_public_userconnection'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userconnection',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('approved', 'Approved'),
                    ('rejected', 'Rejected'),
                ],
                default='pending',
                max_length=15,
            ),
        ),
    ]



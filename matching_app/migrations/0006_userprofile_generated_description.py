from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('matching_app', '0005_alter_userprofile_caste_alter_userprofile_city_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='generated_description',
            field=models.TextField(blank=True, null=True),
        ),
    ]



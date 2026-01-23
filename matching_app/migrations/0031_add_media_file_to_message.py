# Generated manually on 2026-01-20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('matching_app', '0030_remove_session_zoom_meeting_id_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='media_file',
            field=models.FileField(
                blank=True,
                help_text='Media file attached to the message (image, video, audio, document, etc.)',
                null=True,
                upload_to='messages/media/%Y/%m/%d/'
            ),
        ),
    ]

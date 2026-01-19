# Generated manually for replacing Zoom with Google Meet in Session model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('matching_app', '0028_rename_matching_ap_user_id_abc123_idx_matching_ap_user_id_8efd5c_idx'),
    ]

    operations = [
        # Add Google Meet fields
        migrations.AddField(
            model_name='session',
            name='google_meet_link',
            field=models.URLField(blank=True, help_text='Google Meet meeting link', null=True),
        ),
        migrations.AddField(
            model_name='session',
            name='google_meet_event_id',
            field=models.CharField(blank=True, help_text='Google Calendar event ID', max_length=255, null=True),
        ),
        # Note: Zoom fields (zoom_meeting_id, zoom_meeting_url, zoom_meeting_password) 
        # are kept in the model but commented out in code for potential future use
    ]

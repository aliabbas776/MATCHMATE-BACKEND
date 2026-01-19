# Generated manually for Google OAuth Token model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('matching_app', '0026_supportrequest'),
    ]

    operations = [
        migrations.CreateModel(
            name='GoogleOAuthToken',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('access_token', models.TextField(help_text='Google OAuth2 access token')),
                ('refresh_token', models.TextField(blank=True, help_text='Google OAuth2 refresh token for obtaining new access tokens', null=True)),
                ('token_uri', models.URLField(default='https://oauth2.googleapis.com/token', help_text='Token endpoint URI')),
                ('client_id', models.CharField(help_text='Google OAuth2 client ID', max_length=255)),
                ('client_secret', models.CharField(help_text='Google OAuth2 client secret', max_length=255)),
                ('scopes', models.TextField(help_text='Comma-separated list of granted OAuth scopes')),
                ('expires_at', models.DateTimeField(blank=True, help_text='When the access token expires', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(help_text='User who authorized Google Calendar/Meet access', on_delete=django.db.models.deletion.CASCADE, related_name='google_oauth_token', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Google OAuth Token',
                'verbose_name_plural': 'Google OAuth Tokens',
                'indexes': [models.Index(fields=['user', '-updated_at'], name='matching_ap_user_id_abc123_idx')],
            },
        ),
    ]

from django.apps import AppConfig


class MatchingAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'matching_app'
    
    def ready(self):
        """Import signals when the app is ready."""
        import matching_app.signals  # noqa
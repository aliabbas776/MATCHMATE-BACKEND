"""
Management command to sync connections_used field with actual connection request counts.
Usage: python manage.py sync_connections_used
"""
from django.core.management.base import BaseCommand
from matching_app.models import UserConnection, UserSubscription


class Command(BaseCommand):
    help = 'Sync connections_used field with actual connection requests sent from UserConnection table'

    def handle(self, *args, **options):
        subscriptions = UserSubscription.objects.select_related('user', 'plan').all()
        updated_count = 0
        
        for subscription in subscriptions:
            user = subscription.user
            
            # Count actual connection requests sent by this user since last reset (monthly limit)
            query = UserConnection.objects.filter(from_user=user)
            if subscription.last_reset_at:
                query = query.filter(created_at__gte=subscription.last_reset_at)
            actual_connections_sent = query.count()
            
            # Update the connections_used field
            old_count = subscription.connections_used
            subscription.connections_used = actual_connections_sent
            subscription.save(update_fields=['connections_used'])
            
            if old_count != actual_connections_sent:
                updated_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Updated {user.username}: {old_count} → {actual_connections_sent} connection requests'
                    )
                )
            else:
                self.stdout.write(
                    f'  {user.username}: {actual_connections_sent} connection requests (no change)'
                )
        
        self.stdout.write(self.style.SUCCESS(
            f'\n=== Summary ===\n'
            f'Total subscriptions: {subscriptions.count()}\n'
            f'Updated: {updated_count} subscription(s)\n'
        ))


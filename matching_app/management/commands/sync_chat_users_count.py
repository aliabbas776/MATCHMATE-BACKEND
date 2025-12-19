"""
Management command to sync chat_users_count field with actual message counts.
Usage: python manage.py sync_chat_users_count
"""
from django.core.management.base import BaseCommand
from django.db.models import Q
from matching_app.models import Message, UserSubscription


class Command(BaseCommand):
    help = 'Sync chat_users_count field with actual distinct chat users from Message table'

    def handle(self, *args, **options):
        subscriptions = UserSubscription.objects.select_related('user', 'plan').all()
        updated_count = 0
        
        for subscription in subscriptions:
            user = subscription.user
            
            # Count distinct users user has chatted with (combining sent and received)
            sent_to_users = set(
                Message.objects.filter(sender=user)
                .values_list('receiver_id', flat=True)
                .distinct()
            )
            received_from_users = set(
                Message.objects.filter(receiver=user)
                .values_list('sender_id', flat=True)
                .distinct()
            )
            
            # Get all unique user IDs user has chatted with
            total_distinct_chat_users = len(sent_to_users | received_from_users)
            
            # Update the chat_users_count field
            old_count = subscription.chat_users_count
            subscription.chat_users_count = total_distinct_chat_users
            subscription.save(update_fields=['chat_users_count'])
            
            if old_count != total_distinct_chat_users:
                updated_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Updated {user.username}: {old_count} → {total_distinct_chat_users} chat users'
                    )
                )
            else:
                self.stdout.write(
                    f'  {user.username}: {total_distinct_chat_users} chat users (no change)'
                )
        
        self.stdout.write(self.style.SUCCESS(
            f'\n=== Summary ===\n'
            f'Total subscriptions: {subscriptions.count()}\n'
            f'Updated: {updated_count} subscription(s)\n'
        ))


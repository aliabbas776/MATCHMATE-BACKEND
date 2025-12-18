"""
Management command to initialize default subscription plans.
Usage: python manage.py init_subscription_plans
"""
from django.core.management.base import BaseCommand
from matching_app.models import SubscriptionPlan


class Command(BaseCommand):
    help = 'Initialize default subscription plans (Free, Silver, Gold, Platinum)'

    def handle(self, *args, **options):
        plans_data = [
            {
                'tier': SubscriptionPlan.PlanTier.FREE,
                'name': 'Free Plan',
                'description': 'Basic features for free users. Limited to 10 profile views, 5 connection requests, 1 chat user, and 5 sessions.',
                'price': 0.00,
                'duration_days': 30,
                'max_profile_views': 10,  # Limited to 10 profile views
                'max_connections': 5,  # Limited to 5 connection requests
                'max_connection_requests': -1,  # Not used - max_connections is used instead
                'max_chat_users': 1,  # Limited to 1 chat user
                'max_sessions': 5,  # Limited to 5 sessions
                'can_send_messages': True,
                'can_view_photos': True,
                'can_see_who_viewed': False,
                'priority_support': False,
                'advanced_search': False,
                'verified_badge': False,
            },
            {
                'tier': SubscriptionPlan.PlanTier.SILVER,
                'name': 'Silver Plan',
                'description': 'Enhanced features with more profile views and connections.',
                'price': 9.99,
                'duration_days': 30,
                'max_profile_views': 50,
                'max_connections': 20,
                'max_connection_requests': -1,  # Unlimited
                'max_chat_users': -1,  # Unlimited
                'max_sessions': -1,  # Unlimited
                'can_send_messages': True,
                'can_view_photos': True,
                'can_see_who_viewed': True,
                'priority_support': False,
                'advanced_search': True,
                'verified_badge': False,
            },
            {
                'tier': SubscriptionPlan.PlanTier.GOLD,
                'name': 'Gold Plan',
                'description': 'Premium features with unlimited profile views and more connections.',
                'price': 19.99,
                'duration_days': 30,
                'max_profile_views': -1,  # Unlimited
                'max_connections': 50,
                'max_connection_requests': -1,  # Unlimited
                'max_chat_users': -1,  # Unlimited
                'max_sessions': -1,  # Unlimited
                'can_send_messages': True,
                'can_view_photos': True,
                'can_see_who_viewed': True,
                'priority_support': True,
                'advanced_search': True,
                'verified_badge': False,
            },
            {
                'tier': SubscriptionPlan.PlanTier.PLATINUM,
                'name': 'Platinum Plan',
                'description': 'Ultimate features with unlimited everything and premium benefits.',
                'price': 39.99,
                'duration_days': 30,
                'max_profile_views': -1,  # Unlimited
                'max_connections': -1,  # Unlimited
                'max_connection_requests': -1,  # Unlimited
                'max_chat_users': -1,  # Unlimited
                'max_sessions': -1,  # Unlimited
                'can_send_messages': True,
                'can_view_photos': True,
                'can_see_who_viewed': True,
                'priority_support': True,
                'advanced_search': True,
                'verified_badge': True,
            },
        ]

        created_count = 0
        updated_count = 0

        for plan_data in plans_data:
            plan, created = SubscriptionPlan.objects.update_or_create(
                tier=plan_data['tier'],
                defaults=plan_data
            )
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Created {plan.name}')
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'↻ Updated {plan.name}')
                )

        self.stdout.write(self.style.SUCCESS(
            f'\n=== Summary ===\n'
            f'Created: {created_count} plan(s)\n'
            f'Updated: {updated_count} plan(s)\n'
            f'Total: {SubscriptionPlan.objects.count()} plan(s)'
        ))


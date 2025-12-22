"""
Signals for syncing CNIC verification status to UserProfile.
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from .models import CNICVerification, UserProfile


@receiver(pre_save, sender=CNICVerification)
def store_old_status(sender, instance, **kwargs):
    """Store the old status before saving to detect changes."""
    if instance.pk:
        try:
            old_instance = CNICVerification.objects.get(pk=instance.pk)
            instance._old_status = old_instance.status
        except CNICVerification.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None


@receiver(post_save, sender=CNICVerification)
def sync_cnic_status_to_profile(sender, instance, created, **kwargs):
    """
    Sync CNIC verification status to UserProfile whenever CNICVerification is saved.
    This ensures that admin panel changes are reflected in the UserProfile.
    """
    # Check if status actually changed
    old_status = getattr(instance, '_old_status', None)
    if not created and old_status == instance.status:
        # Status didn't change, no need to sync
        return
    
    try:
        profile = instance.user.profile
        # Map CNICVerification status to UserProfile status
        status_mapping = {
            CNICVerification.Status.PENDING: 'pending',
            CNICVerification.Status.VERIFIED: 'verified',
            CNICVerification.Status.REJECTED: 'rejected',
        }
        
        new_status = status_mapping.get(instance.status, 'unverified')
        
        # Always sync to ensure consistency (even if it seems the same)
        profile.cnic_verification_status = new_status
        
        # Update verified_at timestamp
        if instance.status == CNICVerification.Status.VERIFIED:
            profile.cnic_verified_at = timezone.now()
        elif instance.status == CNICVerification.Status.REJECTED:
            profile.cnic_verified_at = None
        
        profile.save(update_fields=['cnic_verification_status', 'cnic_verified_at'])
    except UserProfile.DoesNotExist:
        # Profile doesn't exist yet, skip sync
        pass
    except Exception as e:
        # Log error but don't break the save operation
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Error syncing CNIC status to profile: {e}')


"""
Test script to verify push notifications are working on live server.
Run this on your live server via Django shell or as a management command.
"""
from django.contrib.auth import get_user_model
from matching_app.models import Device, Message
from matching_app.services.notification_examples import send_new_message_notification

User = get_user_model()

def test_push_notification():
    """Test push notification system"""
    
    # 1. Check if receiver has registered FCM token
    print("=" * 60)
    print("STEP 1: Checking receiver's FCM tokens...")
    print("=" * 60)
    
    receiver_id = int(input("Enter receiver user ID: "))
    try:
        receiver = User.objects.get(id=receiver_id)
        print(f"✓ Found receiver: {receiver.username} (ID: {receiver.id})")
        
        devices = Device.objects.filter(user=receiver, is_active=True)
        print(f"✓ Active devices: {devices.count()}")
        
        if devices.count() == 0:
            print("⚠ WARNING: No active devices found for this user!")
            print("   The user needs to register their FCM token first.")
            return
        
        for device in devices:
            print(f"  - Device ID: {device.id}")
            print(f"    Type: {device.device_type}")
            print(f"    Token: {device.fcm_token[:50]}...")
            print(f"    Active: {device.is_active}")
    except User.DoesNotExist:
        print(f"✗ User with ID {receiver_id} not found!")
        return
    
    # 2. Get sender
    print("\n" + "=" * 60)
    print("STEP 2: Getting sender...")
    print("=" * 60)
    
    sender_id = int(input("Enter sender user ID: "))
    try:
        sender = User.objects.get(id=sender_id)
        print(f"✓ Found sender: {sender.username} (ID: {sender.id})")
    except User.DoesNotExist:
        print(f"✗ User with ID {sender_id} not found!")
        return
    
    # 3. Send test notification
    print("\n" + "=" * 60)
    print("STEP 3: Sending test notification...")
    print("=" * 60)
    
    test_message = "This is a test push notification from the live server!"
    print(f"Test message: {test_message}")
    
    result = send_new_message_notification(
        sender_user=sender,
        receiver_user=receiver,
        message_content=test_message
    )
    
    if result:
        print("\n✓ Notification sent successfully!")
        print(f"  Total devices: {result.get('total_devices', 0)}")
        print(f"  Successful: {result.get('successful', 0)}")
        print(f"  Failed: {result.get('failed', 0)}")
        print(f"  Invalid tokens removed: {result.get('invalid_tokens_removed', 0)}")
        
        if result.get('successful', 0) > 0:
            print("\n✅ SUCCESS: Push notification was sent to device(s)!")
        else:
            print("\n⚠ WARNING: Notification was attempted but no devices received it.")
            print("   Check if FCM token is valid and Firebase is configured correctly.")
    else:
        print("\n✗ ERROR: Failed to send notification. Check server logs for details.")
    
    # 4. Check recent messages
    print("\n" + "=" * 60)
    print("STEP 4: Checking recent messages...")
    print("=" * 60)
    
    recent_messages = Message.objects.filter(
        sender=sender,
        receiver=receiver
    ).order_by('-created_at')[:5]
    
    print(f"Recent messages from {sender.username} to {receiver.username}:")
    for msg in recent_messages:
        print(f"  - [{msg.created_at}] {msg.content[:50]}...")
    
    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)

if __name__ == "__main__":
    import os
    import django
    
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'matchmate.settings')
    django.setup()
    
    test_push_notification()



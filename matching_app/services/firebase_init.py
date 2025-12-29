"""
Firebase Admin SDK initialization module.

This module handles the initialization of Firebase Admin SDK using a service account.
It ensures Firebase is initialized only once and handles credential loading securely.
"""
import os
import logging
from pathlib import Path
from django.conf import settings

logger = logging.getLogger(__name__)

# Global variable to store the initialized Firebase app
_firebase_app = None


def get_firebase_app():
    """
    Get or initialize the Firebase Admin SDK app.
    
    This function ensures Firebase is initialized only once using a singleton pattern.
    It loads credentials from either:
    1. A service account JSON file path (FIREBASE_SERVICE_ACCOUNT_PATH)
    2. A service account JSON file content (FIREBASE_SERVICE_ACCOUNT_JSON)
    3. Environment variable containing the JSON content
    
    Returns:
        firebase_admin.App: Initialized Firebase app instance
        
    Raises:
        ValueError: If Firebase credentials are not properly configured
        Exception: If Firebase initialization fails
    """
    global _firebase_app
    
    if _firebase_app is not None:
        return _firebase_app
    
    try:
        import firebase_admin
        from firebase_admin import credentials
        
        # Check if Firebase is already initialized
        try:
            _firebase_app = firebase_admin.get_app()
            logger.info("Firebase app already initialized")
            return _firebase_app
        except ValueError:
            # Firebase not initialized yet, proceed with initialization
            pass
        
        # Load credentials
        cred = None
        
        # Option 1: Service account JSON file path
        service_account_path = getattr(
            settings, 
            'FIREBASE_SERVICE_ACCOUNT_PATH', 
            None
        )
        if service_account_path:
            service_account_path = Path(service_account_path)
            if service_account_path.exists() and service_account_path.is_file():
                cred = credentials.Certificate(str(service_account_path))
                logger.info(f"Firebase credentials loaded from file: {service_account_path}")
            else:
                logger.warning(f"Firebase service account file not found: {service_account_path}")
        
        # Option 2: Service account JSON content (from settings or env)
        if cred is None:
            service_account_json = getattr(
                settings, 
                'FIREBASE_SERVICE_ACCOUNT_JSON', 
                None
            )
            if not service_account_json:
                # Try loading from environment variable
                service_account_json = os.getenv('FIREBASE_SERVICE_ACCOUNT_JSON')
            
            if service_account_json:
                import json
                # If it's a string, try to parse it as JSON
                if isinstance(service_account_json, str):
                    try:
                        service_account_dict = json.loads(service_account_json)
                        cred = credentials.Certificate(service_account_dict)
                        logger.info("Firebase credentials loaded from JSON string")
                    except json.JSONDecodeError:
                        # If JSON parsing fails, try treating it as a file path
                        json_path = Path(service_account_json)
                        if json_path.exists() and json_path.is_file():
                            cred = credentials.Certificate(str(json_path))
                            logger.info(f"Firebase credentials loaded from path in env: {json_path}")
                elif isinstance(service_account_json, dict):
                    cred = credentials.Certificate(service_account_json)
                    logger.info("Firebase credentials loaded from dict")
        
        if cred is None:
            raise ValueError(
                "Firebase credentials not found. Please configure either "
                "FIREBASE_SERVICE_ACCOUNT_PATH or FIREBASE_SERVICE_ACCOUNT_JSON in settings.py"
            )
        
        # Initialize Firebase Admin SDK
        _firebase_app = firebase_admin.initialize_app(cred)
        logger.info("Firebase Admin SDK initialized successfully")
        
        return _firebase_app
        
    except ImportError:
        logger.error("firebase-admin package not installed. Install it with: pip install firebase-admin")
        raise
    except Exception as e:
        logger.error(f"Failed to initialize Firebase: {str(e)}")
        raise


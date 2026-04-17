"""
Firebase Admin SDK initialization.
Initialized once at app startup. Exports Firestore client, Storage bucket, and auth verifier.
This file has no logic — it only initializes and exports clients.
"""
import os
import firebase_admin
from firebase_admin import credentials, firestore, storage, auth


# Module-level clients — populated by initialize_firebase()
db = None
bucket = None


def _build_credentials():
    """Build Firebase credentials from env vars or a local service account file."""
    project_id = os.getenv("FIREBASE_PROJECT_ID")
    private_key = os.getenv("FIREBASE_PRIVATE_KEY")
    client_email = os.getenv("FIREBASE_CLIENT_EMAIL")

    if project_id and private_key and client_email:
        # Secret Manager often stores the private key with escaped newlines.
        private_key = private_key.replace("\\n", "\n")
        return credentials.Certificate({
            "type": "service_account",
            "project_id": project_id,
            "private_key": private_key,
            "client_email": client_email,
            "token_uri": "https://oauth2.googleapis.com/token",
        })

    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "serviceAccountKey.json")
    return credentials.Certificate(cred_path)


def get_db():
    """Return the initialized Firestore client."""
    if db is None:
        raise RuntimeError("Firebase has not been initialized yet")
    return db


def get_bucket():
    """Return the configured Cloud Storage bucket if one is available."""
    if bucket is None:
        raise RuntimeError("Cloud Storage bucket is not configured")
    return bucket


def initialize_firebase():
    """
    Initialize Firebase Admin SDK. Called once from main.py on startup.
    Supports both file-based credentials (local dev) and env-based (Cloud Run).
    """
    global db, bucket

    if firebase_admin._apps:
        # Already initialized
        db = firestore.client()
        bucket_name = os.getenv("GCS_BUCKET_NAME")
        bucket = storage.bucket(bucket_name) if bucket_name else None
        return

    cred = _build_credentials()
    app_options = {}
    bucket_name = os.getenv("GCS_BUCKET_NAME")
    if bucket_name:
        app_options["storageBucket"] = bucket_name

    firebase_admin.initialize_app(cred, app_options or None)
    db = firestore.client()
    bucket = storage.bucket(bucket_name) if bucket_name else None

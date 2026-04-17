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


def initialize_firebase():
    """
    Initialize Firebase Admin SDK. Called once from main.py on startup.
    Uses GOOGLE_APPLICATION_CREDENTIALS env var pointing to serviceAccountKey.json.
    """
    global db, bucket

    if firebase_admin._apps:
        # Already initialized
        db = firestore.client()
        bucket_name = os.getenv("GCS_BUCKET_NAME")
        if bucket_name:
            bucket = storage.bucket()
        return

    cred = credentials.Certificate(os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
    firebase_admin.initialize_app(cred, {
        "storageBucket": os.getenv("GCS_BUCKET_NAME")
    })

    db = firestore.client()
    bucket_name = os.getenv("GCS_BUCKET_NAME")
    if bucket_name:
        bucket = storage.bucket()

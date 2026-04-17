"""
Google Cloud Storage client wrapper.
Upload PDF bytes, return signed URLs valid for 7 days.
"""
from datetime import timedelta
from firebase.firebase_admin import bucket


def upload_pdf(session_id: str, pdf_bytes: bytes) -> str:
    """
    Uploads PDF report bytes to GCS with a session-based filename.
    Returns a signed URL valid for 7 days.
    """
    blob_name = f"reports/{session_id}/home_buying_report.pdf"
    blob = bucket.blob(blob_name)
    blob.upload_from_string(pdf_bytes, content_type="application/pdf")

    signed_url = blob.generate_signed_url(
        version="v4",
        expiration=timedelta(days=7),
        method="GET",
    )
    return signed_url


def get_report_url(session_id: str) -> str:
    """
    Returns a signed URL for an existing report PDF.
    Raises FileNotFoundError if report does not exist.
    """
    blob_name = f"reports/{session_id}/home_buying_report.pdf"
    blob = bucket.blob(blob_name)

    if not blob.exists():
        raise FileNotFoundError(f"No report found for session {session_id}")

    signed_url = blob.generate_signed_url(
        version="v4",
        expiration=timedelta(days=7),
        method="GET",
    )
    return signed_url

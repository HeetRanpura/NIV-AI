# NIV AI Backend

NIV AI is a risk-aware home buying decision intelligence platform for Indian families. This backend provides the deterministic financial engines, Firebase-backed session persistence, FastAPI APIs, WebSocket streaming hooks for the AI roundtable, PDF report generation, and Cloud Run deployment path.

## Architecture

```text
Frontend (Dev 3)
  -> FastAPI routes / WebSocket
  -> Deterministic engines (India costs, affordability, scenarios, risk)
  -> Firestore session persistence
  -> Dev 2 orchestrator for behavioral analysis, presentation, roundtable, verdict
  -> PDF generator / optional GCS upload
```

## Key Backend Responsibilities

- Secure Firebase auth verification with an explicit development-only bypass via `SKIP_AUTH=true`
- Environment-aware CORS: `*` in development, frontend origin only in production
- Deterministic Indian home-buying calculations including PMAY subsidy estimation
- Firestore persistence for sessions, behavioral intake, simulation results, presentation, verdict, and reports
- Direct PDF report downloads that survive backend restarts
- Cloud Run-ready container configuration

## Local Setup

1. Create and activate a Python 3.11 virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and fill in the required values.
4. For local Firebase auth/dev:
   - Set `GOOGLE_APPLICATION_CREDENTIALS` to a local service account JSON path, or
   - Provide `FIREBASE_PROJECT_ID`, `FIREBASE_PRIVATE_KEY`, and `FIREBASE_CLIENT_EMAIL`.
5. Start the API from the backend directory:

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Environment Variables

```env
GEMINI_API_KEY=
ENVIRONMENT=development
FRONTEND_URL=http://localhost:3000
BACKEND_URL=http://localhost:8000
SKIP_AUTH=false

# Local file-based Firebase
GOOGLE_APPLICATION_CREDENTIALS=serviceAccountKey.json

# Cloud Run / Secret Manager Firebase
FIREBASE_PROJECT_ID=
FIREBASE_PRIVATE_KEY=
FIREBASE_CLIENT_EMAIL=

# Optional report uploads
GCS_BUCKET_NAME=

# Cloud Run
PORT=8080
```

## API Summary

- `GET /health`
- `GET /india/defaults`
- `POST /session/start`
- `POST /behavioral/{session_id}`
- `POST /analyze/{session_id}`
- `POST /conversation/{session_id}`
- `GET /session/{session_id}`
- `GET /session/history/{user_id}`
- `GET /report/{session_id}`
- `GET /report/{session_id}/download`
- `WS /roundtable/{session_id}?token=<firebase_id_token>`

## Deterministic Verification

Run the deterministic smoke test:

```bash
PYTHONPYCACHEPREFIX=/tmp python3 backend/test_deterministic.py
```

This verifies:

- India hidden-cost calculations
- EMI affordability math
- Five scenario stress tests
- Composite risk scoring
- PMAY subsidy integration

## Deployment

Build the container:

```bash
docker build -t niv-ai-backend .
```

Example Cloud Run deploy flow:

```bash
docker tag niv-ai-backend gcr.io/<project-id>/niv-ai-backend
docker push gcr.io/<project-id>/niv-ai-backend

gcloud run deploy niv-ai-backend \
  --image gcr.io/<project-id>/niv-ai-backend \
  --region asia-south1 \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars ENVIRONMENT=production,SKIP_AUTH=false,BACKEND_URL=https://<service-url>,FRONTEND_URL=https://<frontend-url>
```

Recommended production secret handling:

- Store `GEMINI_API_KEY` in Secret Manager
- Store Firebase service account fields in Secret Manager
- Inject secrets into Cloud Run as environment variables
- Never commit service account JSON files or `.env` files

## Frontend Integration Notes

- Dev 3 should call `GET /india/defaults` on load to keep UI math aligned with backend policy constants.
- Use `GET /report/{session_id}/download` for instant browser downloads.
- WebSocket auth uses the Firebase ID token in the `token` query param.

## Live Deployment

Add the Cloud Run URL here once deployed:

- Backend: `TBD`
- Frontend: `TBD`

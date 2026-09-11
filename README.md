# PetSinger Backend
Compact Render-ready FastAPI backend.

Build: `pip install -r requirements.txt`
Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`

Environment variables:
- GEMINI_API_KEY
- VISIONSTORY_API_KEY

POST `/v1/generate` as multipart form:
- `pet_image`: image
- `prompt`: text

GET `/v1/status/{video_id}`

The backend keeps keys server-side. It uses Google Lyria 3.5 for original music/vocals, then VisionStory custom avatar + pre-recorded audio for the singing video.

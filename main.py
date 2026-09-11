
import os, base64, tempfile, uuid, mimetypes
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
from google import genai

app=FastAPI(title="PetSinger Backend", version="0.2")from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(CORSMiddleware,allow_origins=["https://peterjonas14-collab.github.io"
    ],allow_credentials=False,allow_methods=["*"],allow_headers=["*"],)


GEMINI=os.getenv("GEMINI_API_KEY","")
VISION=os.getenv("VISIONSTORY_API_KEY","")
VS="https://openapi.visionstory.ai"

@app.get("/health")
def health(): return {"ok":True,"service":"PetSinger"}

async def lyria_song(prompt, image_bytes, image_type):
    if not GEMINI: raise RuntimeError("GEMINI_API_KEY is missing")
    client=genai.Client(api_key=GEMINI)
    # Lyria 3.5 supports text + image inputs and returns audio plus generated lyrics.
    contents=[
        f"""Create an original funny upbeat pop song for a singing pet video.
Topic: {prompt}
Make it family-friendly and catchy. Use original lyrics only; do not imitate any named artist.
Target approximately 15-30 seconds and include a memorable chorus.""",
        {"inline_data":{"mime_type":image_type,"data":image_bytes}},
    ]
    response=client.models.generate_content(model="lyria-3.5", contents=contents)
    audio=None; lyrics=""
    for part in getattr(response,"parts",[]) or []:
        if getattr(part,"text",None): lyrics += part.text
        if getattr(part,"inline_data",None) and getattr(part.inline_data,"data",None):
            audio=part.inline_data.data
    if not audio: raise RuntimeError("Lyria returned no audio")
    return audio, lyrics

def media_ref(data, mime):
    return {"inline_data":{"mime_type":mime,"data":base64.b64encode(data).decode()}}

async def create_avatar(image_bytes, image_type):
    headers={"X-API-Key":VISION,"Content-Type":"application/json"}
    payload={"inline_data":{"mime_type":image_type,"data":base64.b64encode(image_bytes).decode()}}
    async with httpx.AsyncClient(timeout=120) as c:
        r=await c.post(f"{VS}/api/v1/avatar",headers=headers,json=payload)
        r.raise_for_status()
        return r.json()["data"]

async def create_video(avatar_id,audio_bytes):
    headers={"X-API-Key":VISION,"Content-Type":"application/json"}
    payload={
        "model_id":"vs_character_v4",
        "avatar_id":avatar_id,
        "audio_script":{"inline_data":{
            "mime_type":"audio/mpeg",
            "data":base64.b64encode(audio_bytes).decode()
        }},
        "aspect_ratio":"9:16",
        "resolution":"1080p",
        "emotion":"singing",
    }
    async with httpx.AsyncClient(timeout=120) as c:
        r=await c.post(f"{VS}/api/v1/video",headers=headers,json=payload)
        r.raise_for_status()
        return r.json()["data"]

async def video_status(video_id):
    headers={"X-API-Key":VISION}
    async with httpx.AsyncClient(timeout=60) as c:
        r=await c.get(f"{VS}/api/v1/video",headers=headers,params={"video_id":video_id})
        r.raise_for_status()
        return r.json()["data"]

@app.post("/v1/generate")
async def generate(
    pet_image: UploadFile=File(...),
    prompt: str=Form("I'm the Boss of the House"),
):
    if not VISION: raise HTTPException(500,"VISIONSTORY_API_KEY is missing")
    data=await pet_image.read()
    if len(data)>10*1024*1024: raise HTTPException(413,"Pet image must be <=10MB")
    image_type=pet_image.content_type or "image/jpeg"
    try:
        audio,lyrics=await lyria_song(prompt,data,image_type)
        avatar=await create_avatar(data,image_type)
        video=await create_video(avatar["avatar_id"],audio)
        return {"status":"queued","video_id":video["video_id"],"lyrics":lyrics,
                "avatar_id":avatar["avatar_id"]}
    except httpx.HTTPStatusError as e:
        detail=e.response.text[:2000]
        raise HTTPException(502,detail)
    except Exception as e:
        raise HTTPException(502,str(e))

@app.get("/v1/status/{video_id}")
async def status(video_id:str):
    try:
        data=await video_status(video_id)
        return data
    except httpx.HTTPStatusError as e:
        raise HTTPException(502,e.response.text[:2000])

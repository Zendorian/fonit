
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps, ImageFilter
import pytesseract
import io
import json
import os
import requests
import difflib

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
def serve_homepage():
    return FileResponse("static/index.html")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FONTS_CACHE_FILE = "cached_fonts.json"

def get_google_fonts():
    if os.path.exists(FONTS_CACHE_FILE):
        with open(FONTS_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    try:
        url = "https://www.googleapis.com/webfonts/v1/webfonts?key=AIzaSyCjT8DVkZFJwXvxaVKuhJ3xrW0XfRkPfwo"
        response = requests.get(url)
        data = response.json()
        fonts = [
            {
                "name": item['family'],
                "url": f"https://fonts.google.com/specimen/{item['family'].replace(' ', '+')}"
            }
            for item in data.get("items", [])
        ]
        with open(FONTS_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(fonts, f)
        return fonts
    except Exception:
        return [{"name": "Roboto", "url": "https://fonts.google.com/specimen/Roboto"}]

def preprocess_image(image):
    gray = ImageOps.grayscale(image)
    enhanced = gray.filter(ImageFilter.MedianFilter()).point(lambda x: 0 if x < 128 else 255, '1')
    return enhanced

def find_matches(words, fonts):
    matches = {}
    font_names = [f["name"] for f in fonts]
    for word in words:
        close = difflib.get_close_matches(word, font_names, n=5, cutoff=0.4)
        matches[word] = [f for f in fonts if f["name"] in close]
    return matches

@app.post("/identify-font")
async def identify_font(file: UploadFile = File(...)):
    try:
        image_data = await file.read()
        image = Image.open(io.BytesIO(image_data)).convert("RGB")
        image = preprocess_image(image)
        config = r'--psm 6 -c tessedit_char_whitelist=abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
        text = pytesseract.image_to_string(image, config=config).strip()
        print("OCR text:", repr(text))
        if not text:
            return JSONResponse({"words": [], "matches": {}})

        words = list({w for line in text.split("\n") for w in line.strip().split() if w})
        fonts = get_google_fonts()
        matches = find_matches(words, fonts)

        return JSONResponse({"words": words, "matches": matches})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

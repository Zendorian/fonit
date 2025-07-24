from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps, ImageFilter
import pytesseract
import io
import requests
import os
import json

app = FastAPI()

# Serve static files (e.g., logo.png, JS, CSS)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Serve index.html at the root
@app.get("/", response_class=HTMLResponse)
def serve_homepage():
    return FileResponse("static/index.html")

# CORS (optional, good for dev)
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
        url = "https://www.googleapis.com/webfonts/v1/webfonts?key=YOUR_GOOGLE_FONTS_API_KEY"
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
    except Exception as e:
        print("Using fallback font list:", e)
        return [
            {"name": "Roboto", "url": "https://fonts.google.com/specimen/Roboto"},
            {"name": "Open Sans", "url": "https://fonts.google.com/specimen/Open+Sans"},
            {"name": "Lora", "url": "https://fonts.google.com/specimen/Lora"},
        ]

def find_similar_fonts(text, font_list):
    matches = []
    if text:
        for font in font_list:
            name_lower = font['name'].lower()
            if any(word in name_lower for word in text.lower().split()):
                matches.append(font)
    return matches if matches else font_list[:5]

def preprocess_image(image):
    gray = ImageOps.grayscale(image)
    enhanced = gray.filter(ImageFilter.MedianFilter()).point(lambda x: 0 if x < 128 else 255, '1')
    return enhanced

@app.post("/identify-font")
async def identify_font(file: UploadFile = File(...)):
    try:
        image_data = await file.read()
        image = Image.open(io.BytesIO(image_data)).convert("RGB")
        clean_image = preprocess_image(image)

        extracted_text = pytesseract.image_to_string(clean_image).strip()
        extracted_text = extracted_text.split("\n")[0] if extracted_text else "Unknown"

        fonts = get_google_fonts()
        matches = find_similar_fonts(extracted_text, fonts)

        return JSONResponse({
            "text": extracted_text,
            "matches": matches
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

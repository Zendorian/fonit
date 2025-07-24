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
import difflib

app = FastAPI()

# Serve frontend
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
def serve_homepage():
    return FileResponse("static/index.html")

# CORS (optional)
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
    except Exception as e:
        print("Font API fallback:", e)
        return [
            {"name": "Roboto", "url": "https://fonts.google.com/specimen/Roboto"},
            {"name": "Open Sans", "url": "https://fonts.google.com/specimen/Open+Sans"},
            {"name": "Lora", "url": "https://fonts.google.com/specimen/Lora"},
        ]

def find_similar_fonts(text, font_list):
    if not text:
        return font_list[:5]
    font_names = [f['name'] for f in font_list]
    matches = difflib.get_close_matches(text, font_names, n=5, cutoff=0.4)
    return [f for f in font_list if f['name'] in matches]

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

        # Optional: save for debugging
        # clean_image.save("last_uploaded.png")

        # OCR with config
        custom_config = r'--psm 7 -c tessedit_char_whitelist=abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
        extracted_text = pytesseract.image_to_string(clean_image, config=custom_config).strip()
        print("OCR Result:", repr(extracted_text))

        # Sanitize OCR result
        extracted_text = extracted_text.split("\n")[0] if extracted_text else ""

        if not extracted_text:
            return JSONResponse({"text": "No text found", "matches": []})

        fonts = get_google_fonts()
        matches = find_similar_fonts(extracted_text, fonts)

        return JSONResponse({
            "text": extracted_text,
            "matches": matches
        })

    except Exception as e:
        print("Error:", e)
        return JSONResponse(status_code=500, content={"error": str(e)})


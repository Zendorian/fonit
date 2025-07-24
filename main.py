from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps, ImageFilter
import pytesseract
import io
import requests
import os
import json

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

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
    if image.mode in ("RGBA", "LA"):
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[3])
        image = background

    gray = ImageOps.grayscale(image)
    contrast = ImageOps.autocontrast(gray)
    sharpened = contrast.filter(ImageFilter.SHARPEN)
    thresholded = sharpened.point(lambda x: 0 if x < 160 else 255, '1')
    return thresholded

@app.post("/identify-font")
async def identify_font(file: UploadFile = File(...)):
    try:
        image_data = await file.read()
        image = Image.open(io.BytesIO(image_data)).convert("RGBA")
        clean_image = preprocess_image(image)
        clean_image.save("debug_cropped.png")

        extracted_text = pytesseract.image_to_string(clean_image, lang="eng").strip()
        print("🧠 OCR result:", repr(extracted_text))

        if not extracted_text or len(extracted_text.strip()) == 0:
            extracted_text = "Unknown"

        fonts = get_google_fonts()
        matches = find_similar_fonts(extracted_text, fonts)

        return JSONResponse({
            "text": extracted_text,
            "matches": matches
        })

    except Exception as e:
        print("❌ Error:", e)
        return JSONResponse(status_code=500, content={"error": str(e)})

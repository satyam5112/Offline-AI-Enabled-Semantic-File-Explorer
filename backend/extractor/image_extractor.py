import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import os

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def enhance_image(img):
    """Enhance image quality for better OCR"""
    
    # ✅ Convert to grayscale
    img = img.convert("L")
    
    # ✅ Increase size for better OCR (2x upscale)
    width, height = img.size
    img = img.resize((width * 2, height * 2), Image.LANCZOS)
    
    # ✅ Increase contrast
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)
    
    # ✅ Increase sharpness
    enhancer = ImageEnhance.Sharpness(img)
    img = enhancer.enhance(2.0)
    
    # ✅ Remove noise
    img = img.filter(ImageFilter.MedianFilter(size=3))
    
    return img

def try_all_rotations(img):
    """Try all rotations and return best result"""
    best_text = ""
    best_len = 0

    for angle in [0, 90, 180, 270]:
        rotated = img.rotate(angle, expand=True)
        try:
            # ✅ Use better OCR config
            config = "--oem 3 --psm 6"
            text = pytesseract.image_to_string(rotated, config=config)
            if len(text.strip()) > best_len:
                best_text = text
                best_len = len(text.strip())
        except:
            continue

    return best_text

def extract_image(file_path):
    try:
        img = Image.open(file_path)

        # ✅ Try with enhancement first
        enhanced = enhance_image(img)
        text = try_all_rotations(enhanced)

        # ✅ If still poor, try original without enhancement
        if len(text.strip()) < 50:
            text = try_all_rotations(img.convert("L"))

        if len(text.strip()) < 10:
            print(f"⚠️ Low text extracted: {file_path}")
            return ""

        print(f"✅ Image extracted: {len(text)} chars")
        return text

    except Exception as e:
        print(f"❌ Image extraction error: {e}")
        return ""
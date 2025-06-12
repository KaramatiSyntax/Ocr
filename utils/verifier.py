import pytesseract
import cv2
import numpy as np
from PIL import Image

def extract_text(image: Image.Image) -> str:
    return pytesseract.image_to_string(image)

def check_blur(image: Image.Image) -> bool:
    img = np.array(image.convert('L'))
    laplacian_var = cv2.Laplacian(img, cv2.CV_64F).var()
    return laplacian_var < 100  # Example threshold

def verify_logo(image: Image.Image) -> bool:
    # Dummy logo check for example
    return True

def analyze_payment_image(image: Image.Image) -> dict:
    text = extract_text(image)
    blur = check_blur(image)
    logo = verify_logo(image)

    return {
        "text": text.strip(),
        "is_blurry": blur,
        "logo_verified": logo
    }
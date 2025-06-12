import pytesseract
import numpy as np
import cv2

def extract_payment_info(image):
    text = pytesseract.image_to_string(image)
    return {"extracted_text": text}

def verify_logo(image):
    return True  # Dummy, replace with actual logo check

def detect_photoshop(image):
    return False  # Dummy, replace with actual photoshop detection logic

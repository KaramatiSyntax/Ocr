import pytesseract
pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'

import re
import numpy as np
import cv2
from PIL import Image
from PIL.ExifTags import TAGS

def extract_payment_info(image):
    text = pytesseract.image_to_string(image)

    result = {
        "raw_text": text,
        "amount": None,
        "transaction_id": None,
        "from": None,
        "to": None,
        "date": None,
        "time": None,
        "status": None
    }

    # Amount (₹123.45 or Rs. 123.45)
    amount_match = re.search(r"(₹|Rs\.?)\s?(\d+[.,]?\d{0,2})", text)
    if amount_match:
        result["amount"] = amount_match.group(0)

    # Transaction ID / UTR
    txn_match = re.search(r"(UTR|Ref(?:erence)? No.?|Txn ID|Transaction ID)[^\d]*(\w{8,})", text, re.IGNORECASE)
    if txn_match:
        result["transaction_id"] = txn_match.group(2)

    # From
    from_match = re.search(r"From\s*[:\-]?\s*(.*)", text)
    if from_match:
        result["from"] = from_match.group(1).strip()

    # To
    to_match = re.search(r"To\s*[:\-]?\s*(.*)", text)
    if to_match:
        result["to"] = to_match.group(1).strip()

    # Date
    date_match = re.search(r"\b\d{2}/\d{2}/\d{4}\b", text)
    if date_match:
        result["date"] = date_match.group(0)

    # Time
    time_match = re.search(r"\b\d{1,2}:\d{2}(?:\s?[AP]M)?\b", text, re.IGNORECASE)
    if time_match:
        result["time"] = time_match.group(0)

    # Status
    status_match = re.search(r"(Paid|Successful|Completed|Failed|Pending|Cancelled)", text, re.IGNORECASE)
    if status_match:
        result["status"] = status_match.group(0).capitalize()

    return result


def verify_logo(image):
    try:
        screenshot = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        logo = cv2.imread('static/upi_logo.png')
        if logo is None:
            return False

        result = cv2.matchTemplate(screenshot, logo, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)

        return max_val > 0.8  # 80% similarity threshold
    except Exception as e:
        return False


def detect_photoshop(image):
    try:
        exif_data = image._getexif()
        if not exif_data:
            return True  # No EXIF = suspicious (could be edited)

        suspicious_tags = ['Software', 'ProcessingSoftware']
        for tag_id, value in exif_data.items():
            tag = TAGS.get(tag_id, tag_id)
            if tag in suspicious_tags and 'Adobe' in str(value):
                return True  # Possible Photoshop

        return False
    except Exception:
        return True  # Error while reading = suspicious

def detect_color_status(image):
    """Detects color patterns typically associated with payment status."""
    try:
        # Convert to OpenCV image
        img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        img_hsv = cv2.cvtColor(img_cv, cv2.COLOR_BGR2HSV)

        # Define color ranges for status
        color_ranges = {
            "Success": ((35, 40, 40), (85, 255, 255)),  # Green range
            "Failed": ((0, 50, 50), (10, 255, 255)),    # Red range (lower)
            "Pending": ((20, 100, 100), (30, 255, 255)) # Yellow range
        }

        detected = []

        for status, (lower, upper) in color_ranges.items():
            mask = cv2.inRange(img_hsv, np.array(lower), np.array(upper))
            coverage = cv2.countNonZero(mask) / (img_hsv.shape[0] * img_hsv.shape[1])
            if coverage > 0.01:  # At least 1% of image is this color
                detected.append(status)

        return detected or ["Unknown"]
    except Exception:
        return ["Error"]

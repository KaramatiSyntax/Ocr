import pytesseract
import re
import numpy as np
import cv2
from PIL import Image
from PIL.ExifTags import TAGS

# Better logic based on visual layout
def advanced_parse_payment_text(text):
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

    # Time detection (more reliable)
    time_match = re.search(r"\b(\d{1,2}:\d{2}\s?[AP]M?)\b", text, re.IGNORECASE)
    if time_match:
        result["time"] = time_match.group(1).strip()

    # Transaction ID (usually starts with T)
    txn_match = re.search(r"\bT\d{18,}\b", text)
    if txn_match:
        result["transaction_id"] = txn_match.group(0)

    # Amount detection near "Received from" or "Credited"
    amount_match = re.search(r"Received from.*?(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)", text, re.DOTALL)
    if amount_match:
        result["amount"] = amount_match.group(1).replace(",", "")

    # UTR backup
    utr_match = re.search(r"\bUTR[:\s]*([0-9]{10,})", text)
    if utr_match and not result["transaction_id"]:
        result["transaction_id"] = utr_match.group(1)

    # From person
    from_match = re.search(r"Received from\s+([A-Za-z\s]+?)\s+\d", text)
    if from_match:
        result["from"] = from_match.group(1).strip()

    # Banking name
    bank_match = re.search(r"Banking Name\s*:\s*([A-Za-z\s]+)", text)
    if bank_match:
        result["to"] = bank_match.group(1).strip()

    # Status check
    if "Transaction Successful" in text:
        result["status"] = "Success"
    elif "Failed" in text:
        result["status"] = "Failed"
    elif "Pending" in text:
        result["status"] = "Pending"
    else:
        result["status"] = "Unknown"

    return result


def extract_payment_info(image):
    text = pytesseract.image_to_string(image)
    return advanced_parse_payment_text(text)


def verify_logo(image):
    try:
        screenshot = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        logo = cv2.imread('static/upi_logo.png')
        if logo is None:
            return False
        result = cv2.matchTemplate(screenshot, logo, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)
        return max_val > 0.8
    except Exception:
        return False


def detect_photoshop(image):
    try:
        exif_data = image._getexif()
        if not exif_data:
            return True
        for tag_id, value in exif_data.items():
            tag = TAGS.get(tag_id, tag_id)
            if tag in ['Software', 'ProcessingSoftware'] and 'Adobe' in str(value):
                return True
        return False
    except Exception:
        return True


def detect_color_status(image):
    try:
        img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        img_hsv = cv2.cvtColor(img_cv, cv2.COLOR_BGR2HSV)
        color_ranges = {
            "Success": ((35, 40, 40), (85, 255, 255)),   # Green
            "Failed": ((0, 50, 50), (10, 255, 255)),     # Red
            "Pending": ((20, 100, 100), (30, 255, 255))  # Yellow
        }
        detected = []
        for status, (lower, upper) in color_ranges.items():
            mask = cv2.inRange(img_hsv, np.array(lower), np.array(upper))
            coverage = cv2.countNonZero(mask) / (img_hsv.shape[0] * img_hsv.shape[1])
            if coverage > 0.01:
                detected.append(status)
        return detected or ["Unknown"]
    except Exception:
        return ["Error"]

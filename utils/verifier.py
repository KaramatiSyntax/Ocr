import pytesseract
import re
import numpy as np
import cv2
from PIL import Image
from PIL.ExifTags import TAGS
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Preprocess image before OCR ---
def preprocess_for_ocr(image):
    img = np.array(image.convert("RGB"))
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    gray = cv2.bilateralFilter(gray, 11, 17, 17)
    _, thresh = cv2.threshold(gray, 130, 255, cv2.THRESH_BINARY)
    return thresh

# --- Main Extraction Function ---
def extract_payment_info(image):
    preprocessed = preprocess_for_ocr(image)
    text = pytesseract.image_to_string(preprocessed)
    logging.info(f"OCR extracted text:\n{text[:500]}...")
    return advanced_parse_payment_text(text)

# --- Main Parsing Logic ---
def advanced_parse_payment_text(text):
    result = {
        "raw_text": text,
        "amount": None,
        "transaction_id": None,
        "upi_ref_no": None,
        "order_id": None,
        "utr": None,
        "google_transaction_id": None,
        "upi_transaction_id": None,
        "from_person": None,
        "from_upi_id": None,
        "from_phone_number": None,
        "from_bank": None,
        "to_person": None,
        "to_upi_id": None,
        "to_phone_number": None,
        "to_bank_name": None,
        "date": None,
        "time": None,
        "status": "Unknown",
        "payment_app": "Unknown"
    }

    normalized_text = text.lower().replace("\n", " ")

    # --- Payment App Detection ---
    if "paytm" in normalized_text:
        result["payment_app"] = "Paytm"
    elif "phonepe" in normalized_text or "phone pe" in normalized_text:
        result["payment_app"] = "PhonePe"
    elif "google pay" in normalized_text or "gpay" in normalized_text:
        result["payment_app"] = "Google Pay"

    # --- Status Detection ---
    if re.search(r"(success|completed|complete|paid successfully|transaction successful|you paid|payment done)", normalized_text):
        result["status"] = "Success"
    elif re.search(r"(failed|failure|declined|cancelled)", normalized_text):
        result["status"] = "Failed"
    elif re.search(r"(pending|processing)", normalized_text):
        result["status"] = "Pending"

    # --- Amount Detection ---
    cleaned_text = text.replace(",", "").replace("INR", "₹").replace("Rs.", "₹").replace("Rs", "₹")
    possible_amounts = []

    amount_patterns = [
        r"[₹]\s*([0-9]{2,7}(?:\.\d{1,2})?)",
        r"(?i)(?:amount|paid|debited|credited|received)\s*[:\-]?\s*₹?\s*([0-9]{2,7}(?:\.\d{1,2})?)"
    ]
    for pattern in amount_patterns:
        for match in re.findall(pattern, cleaned_text, flags=re.IGNORECASE):
            try:
                amt = float(match)
                if 1 <= amt <= 1000000:
                    possible_amounts.append(amt)
            except:
                continue
    if not possible_amounts:
        fallback = re.findall(r"\b([0-9]{3,7}(?:\.\d{1,2})?)\b", cleaned_text)
        for match in fallback:
            try:
                amt = float(match)
                if 1 <= amt <= 1000000:
                    possible_amounts.append(amt)
            except:
                continue
    if possible_amounts:
        result["amount"] = max(possible_amounts)
        logging.info(f"Detected amount: ₹{result['amount']}")
    else:
        logging.warning("Amount not detected.")

    # --- Date & Time ---
    datetime_combined_match = re.search(r"(\d{1,2}:\d{2}(?::\d{2})?\s*[ap]m?)\s+(?:on|at)?\s*(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})", text, re.IGNORECASE)
    if datetime_combined_match:
        result["time"] = datetime_combined_match.group(1).strip()
        result["date"] = datetime_combined_match.group(2).strip()
    else:
        date_patterns = [
            r"\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4})\b",
            r"\b(\d{1,2}/\d{1,2}/\d{2,4})\b",
            r"\b(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})\b"
        ]
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                result["date"] = match.group(1).strip()
                break

        time_match = re.search(r"\b(\d{1,2}:\d{2}(?::\d{2})?\s*[AP]M?)\b", text, re.IGNORECASE)
        if time_match:
            result["time"] = time_match.group(1).strip()

    # --- ID Detection ---
    id_patterns = {
        "transaction_id": r"(?:Transaction ID|TID|Txn ID|Trans ID)[:\s]*([A-Za-z0-9\-]+)",
        "upi_ref_no": r"(?:UPI Ref No|UPI Ref|Reference No)[:\s]*([0-9]+)",
        "order_id": r"(?:Order ID|Order No)[:\s]*([0-9]+)",
        "utr": r"(?:UTR|UTR No)[:\s]*([0-9]{10,})",
        "google_transaction_id": r"(?:Google transaction ID|Google Txn ID)[:\s]*([A-Za-z0-9\-]+)",
        "upi_transaction_id": r"(?:UPI transaction ID|UPI Txn ID)[:\s]*([0-9]+)"
    }
    for key, pattern in id_patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result[key] = match.group(1).strip()

    if not any([result[k] for k in ["transaction_id", "upi_ref_no", "utr", "order_id", "google_transaction_id", "upi_transaction_id"]]):
        generic = re.search(r"\b([A-Z0-9]{12,})\b", text)
        if generic:
            result["transaction_id"] = generic.group(1)

    # --- From / To People & UPI IDs ---
    # TO:
    to_match = re.search(r"To[:\s]*([A-Z\s]+)\s+Google Pay\s*[•\-]?\s*([a-zA-Z0-9.\-_]+@[a-zA-Z0-9.\-_]+)", text, re.IGNORECASE)
    if to_match:
        result["to_person"] = to_match.group(1).strip()
        result["to_upi_id"] = to_match.group(2).strip()

    # FROM:
    from_match = re.search(r"From[:\s]*([A-Z\s]+)\s+Google Pay\s*[•\-]?\s*([a-zA-Z0-9.\-_]+@[a-zA-Z0-9.\-_]+)", text, re.IGNORECASE)
    if from_match:
        result["from_person"] = from_match.group(1).strip()
        result["from_upi_id"] = from_match.group(2).strip()

    # Bank
    bank_match = re.search(r"(Punjab National Bank|HDFC Bank|SBI|Airtel Payments Bank|ICICI Bank)", text, re.IGNORECASE)
    if bank_match:
        result["to_bank_name"] = bank_match.group(1).strip()

    return result

# --- Photoshop Detection ---
def detect_photoshop(image):
    try:
        exif_data = image._getexif()
        if not exif_data:
            return False
        for tag_id, value in exif_data.items():
            tag = TAGS.get(tag_id, tag_id)
            if tag in ['Software', 'ProcessingSoftware', 'CreatorTool']:
                if any(x in str(value) for x in ["Adobe", "Photoshop", "GIMP", "Fotor"]):
                    return True
        return False
    except:
        return False

# --- Verification Logic ---
def determine_verification_status(extracted_data):
    passed, total = 0, 6
    reasons = []
    current_time = datetime.now()
    paid_to_target = "VINAYAK KUMAR SHUKLA"

    # 1. Status
    if extracted_data.get("status") == "Success":
        passed += 1
    else:
        reasons.append("Status is not successful.")

    # 2. Amount
    if isinstance(extracted_data.get("amount"), (int, float)):
        passed += 1
    else:
        reasons.append("Amount is invalid.")

    # 3. Transaction ID
    if any([extracted_data.get(k) for k in ["transaction_id", "upi_ref_no", "utr", "order_id", "google_transaction_id", "upi_transaction_id"]]):
        passed += 1
    else:
        reasons.append("Missing transaction ID.")

    # 4. Paid to correct person
    if (extracted_data.get("to_person") or "").strip().upper() == paid_to_target.strip().upper():
        passed += 1
    else:
        reasons.append("Paid-to person does not match.")

    # 5. Recent Time
    date_str, time_str = extracted_data.get("date"), extracted_data.get("time")
    valid_time = False
    if date_str and time_str:
        dt_formats = [
            "%d %b %Y %I:%M %p", "%d %B %Y %I:%M %p",
            "%d/%m/%Y %I:%M %p", "%d %b %Y %H:%M", "%d %B %Y %H:%M"
        ]
        dt_full = f"{date_str} {time_str}"
        for fmt in dt_formats:
            try:
                parsed = datetime.strptime(dt_full, fmt)
                diff = current_time - parsed
                if timedelta(0) <= diff <= timedelta(hours=24):
                    valid_time = True
                    break
                elif diff < timedelta(0):
                    reasons.append("Date/time is in future.")
                else:
                    reasons.append("Date/time too old.")
            except:
                continue
    if valid_time:
        passed += 1
    else:
        reasons.append("Invalid or missing date/time.")

    # 6. Photoshop
    if extracted_data.get("photoshop_detected"):
        reasons.append("Possible Photoshop manipulation.")
    else:
        passed += 1

    percentage = round((passed / total) * 100, 2)
    verified = percentage >= 80 and "Photoshop" not in "".join(reasons)

    return {
        "verified": verified,
        "verified_percentage": percentage,
        "reasons_for_false": reasons if not verified else []
    }

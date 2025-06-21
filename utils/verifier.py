import pytesseract
import re
import logging
from PIL.ExifTags import TAGS
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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

    if re.search(r"(successful|success|completed|paid successfully|transaction successful)", normalized_text):
        result["status"] = "Success"
    elif re.search(r"(failed|failure)", normalized_text):
        result["status"] = "Failed"
    elif re.search(r"(pending)", normalized_text):
        result["status"] = "Pending"

    if "paytm" in normalized_text and "@paytm" in normalized_text:
        result["payment_app"] = "Paytm"
    elif "phonepe" in normalized_text or "phone pe" in normalized_text:
        result["payment_app"] = "PhonePe"
    elif "google pay" in normalized_text or "gpay" in normalized_text:
        result["payment_app"] = "Google Pay"
    elif "punjab national bank" in normalized_text:
        result["payment_app"] = "Google Pay"
    elif "hdfc bank" in normalized_text:
        result["payment_app"] = "Paytm"

    # -- NEW ₹-BASED AMOUNT DETECTION --
    def extract_amount_with_rupee_symbol(text):
        normalized = text.replace(",", "").replace("INR", "₹").replace("Rs.", "₹").replace("Rs", "₹")
        matches = re.findall(r'[₹]\s*([0-9]{2,7}(?:\.\d{1,2})?)', normalized)
        amounts = []
        for match in matches:
            try:
                val = float(match)
                if 10 <= val <= 100000:
                    amounts.append(val)
            except:
                continue
        return max(amounts) if amounts else None

    result["amount"] = extract_amount_with_rupee_symbol(text)
    if result["amount"]:
        logging.info(f"Amount detected: ₹{result['amount']}")
    else:
        logging.warning("No valid amount detected using ₹ symbol.")

    # -- DATE AND TIME DETECTION --
    datetime_combined_match = re.search(r"(\d{1,2}:\d{2}(?::\d{2})?\s*[ap]m?)\s+(?:on|at)?\s*(\d{1,2}\s+\w+\s+\d{4})", text, re.IGNORECASE)
    if datetime_combined_match:
        result["time"] = datetime_combined_match.group(1).strip()
        result["date"] = datetime_combined_match.group(2).strip()
    else:
        for pattern in [r"\b(\d{1,2} \w+ \d{4})\b", r"\b(\d{1,2}/\d{1,2}/\d{2,4})\b"]:
            match = re.search(pattern, text)
            if match:
                result["date"] = match.group(1)
                break
        match = re.search(r"\b(\d{1,2}:\d{2}(?::\d{2})?\s*[ap]m?)\b", text, re.IGNORECASE)
        if match:
            result["time"] = match.group(1)

    # -- TRANSACTION IDS --
    txn_id_patterns = {
        "transaction_id": r"(?:Transaction ID|Txn ID)[:\s]*([A-Za-z0-9-]+)",
        "upi_ref_no": r"(?:UPI Ref No|Reference No)[:\s]*([0-9]+)",
        "order_id": r"(?:Order ID|Order No)[:\s]*([0-9]+)",
        "utr": r"(?:UTR)[:\s]*([0-9]{10,})",
        "google_transaction_id": r"(?:Google transaction ID)[:\s]*([A-Za-z0-9-]+)",
        "upi_transaction_id": r"(?:UPI transaction ID)[:\s]*([0-9]+)"
    }

    for key, pattern in txn_id_patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result[key] = match.group(1).strip()

    # -- PERSON DETAILS --
    if "From Vijay Kumarvijay" in text:
        result["from_person"] = "Vijay Kumarvijay"
    else:
        match = re.search(r"From\s+([A-Za-z\s.]+)", text)
        if match:
            result["from_person"] = match.group(1).strip()

    match = re.search(r"([a-zA-Z0-9.\-_]+@[a-zA-Z0-9.\-_]+)", text)
    if match:
        result["from_upi_id"] = match.group(1).strip()

    match = re.search(r"To:\s*([A-Za-z\s.]+)", text)
    if match:
        result["to_person"] = match.group(1).strip()

    return result


def detect_photoshop(image):
    try:
        exif_data = image._getexif()
        if not exif_data:
            return False
        for tag_id, value in exif_data.items():
            tag = TAGS.get(tag_id, tag_id)
            if tag in ['Software', 'ProcessingSoftware']:
                if 'Adobe' in str(value) or 'Photoshop' in str(value) or 'GIMP' in str(value):
                    logging.warning(f"Editing software '{value}' detected.")
                    return True
        return False
    except Exception as e:
        logging.error(f"Photoshop check failed: {e}")
        return False


def determine_verification_status(extracted_data):
    passed_checks = 0
    total_checks = 6
    reasons = []
    target_paid_to = "VINAYAK KUMAR SHUKLA"
    current_time = datetime.now()

    if extracted_data.get("status") in ["Success", "Completed"]:
        passed_checks += 1
    else:
        reasons.append("Status not completed")

    if extracted_data.get("amount"):
        passed_checks += 1
    else:
        reasons.append("Amount missing")

    if any(extracted_data.get(k) for k in ["transaction_id", "upi_ref_no", "utr", "order_id", "google_transaction_id", "upi_transaction_id"]):
        passed_checks += 1
    else:
        reasons.append("No transaction ID found")

    if extracted_data.get("to_person", "").upper() == target_paid_to:
        passed_checks += 1
    else:
        reasons.append(f"Paid-to person is not {target_paid_to}")

    try:
        dt_str = f"{extracted_data.get('date')} {extracted_data.get('time')}"
        parsed = datetime.strptime(dt_str, "%d %b %Y %I:%M %p")
        if timedelta(0) <= current_time - parsed <= timedelta(hours=24):
            passed_checks += 1
        else:
            reasons.append("Screenshot too old or in future")
    except:
        reasons.append("Date/time parsing failed")

    if not extracted_data.get("photoshop_detected", False):
        passed_checks += 1
    else:
        reasons.append("Photoshop detected")

    verified = passed_checks >= 5
    percent = round(passed_checks / total_checks * 100, 2)
    return {
        "verified": verified,
        "verified_percentage": percent,
        "reasons_for_false": reasons if not verified else []
    }


def extract_payment_info(image):
    text = pytesseract.image_to_string(image)
    data = advanced_parse_payment_text(text)
    return data

import pytesseract
import re
import numpy as np
import cv2
from PIL import Image
from PIL.ExifTags import TAGS
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def extract_payment_info(image: Image.Image) -> dict:
    """Extracts OCR text from the image and parses structured payment info."""
    text = pytesseract.image_to_string(image)
    logging.info(f"OCR extracted text:\n{text[:500]}...")
    return advanced_parse_payment_text(text)


def detect_photoshop(image: Image.Image) -> bool:
    """Checks for signs of Photoshop or editing in EXIF metadata."""
    try:
        exif_data = image._getexif()
        if not exif_data:
            logging.info("No EXIF data found. Might be original or edited without metadata.")
            return False

        for tag_id, value in exif_data.items():
            tag = TAGS.get(tag_id, tag_id)
            if tag in ['Software', 'ProcessingSoftware', 'CreatorTool']:
                if any(editor in str(value) for editor in ['Adobe', 'Photoshop', 'GIMP', 'Fotor']):
                    logging.warning(f"Editing software '{value}' detected.")
                    return True

        logging.info("No signs of editing software in EXIF.")
        return False

    except Exception as e:
        logging.error(f"Error during Photoshop detection: {e}")
        return False


def advanced_parse_payment_text(text: str) -> dict:
    """Parses raw OCR payment text into structured data."""
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

    normalized = text.lower().replace("\n", " ")

    # Status detection
    if re.search(r"(successful|success|completed|paid successfully|transaction successful)", normalized):
        result["status"] = "Success"
    elif re.search(r"(failed|failure)", normalized):
        result["status"] = "Failed"
    elif "pending" in normalized:
        result["status"] = "Pending"

    # Payment app detection
    if "paytm" in normalized and "@paytm" in normalized:
        result["payment_app"] = "Paytm"
    elif "phonepe" in normalized or "phone pe" in normalized:
        result["payment_app"] = "PhonePe"
    elif any(x in normalized for x in ["google pay", "gpay", "punjab national bank"]):
        result["payment_app"] = "Google Pay"
    elif "hdfc bank" in normalized:
        result["payment_app"] = "Paytm"

    # Amount detection
    amount_match = re.search(r"(\d{1,3}(?:,\d{3})*(?:\.\d{1,2}?))", text)
    if amount_match:
        try:
            result["amount"] = float(amount_match.group(1).replace(",", ""))
        except ValueError:
            logging.warning(f"Could not convert amount: {amount_match.group(1)}")

    if not result["amount"]:
        for pattern in [
            r"[₹]\s*(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)",
            r"(?:rs\.?|amount|paid|received|debit(?:ed)?|credit(?:ed)?)\s*:?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)",
        ]:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    result["amount"] = float(match.group(1).replace(",", ""))
                    break
                except ValueError:
                    continue

    # Date/Time detection
    dt_match = re.search(
        r"(\d{1,2}:\d{2}(?::\d{2})?\s*[ap]m?)\s+(?:on|at)?\s*(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})",
        text, re.IGNORECASE)
    if dt_match:
        result["time"], result["date"] = dt_match.group(1).strip(), dt_match.group(2).strip()
    else:
        date_patterns = [
            r"\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4})\b",
            r"\b(\d{1,2}/\d{1,2}/\d{2,4})\b",
            r"\b(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})\b"
        ]
        for dp in date_patterns:
            dm = re.search(dp, text)
            if dm:
                result["date"] = dm.group(1).strip()
                break
        tm = re.search(r"\b(\d{1,2}:\d{2}(?::\d{2})?\s*[AP]M?)\b", text, re.IGNORECASE)
        if tm:
            result["time"] = tm.group(1).strip()

    # Transaction ID fields
    txn_id_patterns = {
        "transaction_id": r"(?:Transaction ID|TID|Txn ID|Trans ID)[:\s]*([A-Za-z0-9-]+)",
        "upi_ref_no": r"(?:UPI Ref No|Reference No)[:\s]*([0-9]+)",
        "order_id": r"(?:Order ID|Order No)[:\s]*([0-9]+)",
        "utr": r"(?:UTR|UTR No)[:\s]*([0-9]{10,})",
        "google_transaction_id": r"(?:Google transaction ID|Google Txn ID)[:\s]*([A-Za-z0-9-]+)",
        "upi_transaction_id": r"(?:UPI transaction ID|UPI Txn ID)[:\s]*([0-9]+)"
    }
    for key, pattern in txn_id_patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result[key] = match.group(1).strip()

    if not any(result[k] for k in ["transaction_id", "upi_ref_no", "utr", "order_id", "google_transaction_id", "upi_transaction_id"]):
        generic_txn_match = re.search(r"\b([A-Z0-9]{12,})\b", text)
        if generic_txn_match:
            result["transaction_id"] = generic_txn_match.group(1)

    # From Person / UPI / Phone
    from_person = re.search(r"From\s*([A-Za-z\s.]+?)(?:\s*\+?\d{10}|\s*UPI ID:|\s*Bank|\n|$)", text, re.IGNORECASE)
    if from_person:
        result["from_person"] = from_person.group(1).strip()

    upi_match = re.search(r"(?:From\s+.*?|Google Pay\s+)?([a-zA-Z0-9.\-_]+@[a-zA-Z0-9.\-_]+)", text)
    if upi_match:
        result["from_upi_id"] = upi_match.group(1).strip()

    phone_match = re.search(r"(?:From|Sender):\s*.*?(\+?\d{2}\s?\d{10}|\d{10})", text)
    if phone_match:
        result["from_phone_number"] = phone_match.group(1).strip()

    # To Person
    for pattern in [
        r"To:\s*([A-Za-z\s.]+?)(?:\n|UPI ID:|Bank|$)",
        r"Paid to\s*([A-Za-z\s.]+?)(?:\n|\+?\d{10}|UPI ID:|Bank|$)",
        r"Banking Name\s*:\s*([A-Za-z\s]+)",
    ]:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            person = match.group(1).strip()
            person = re.sub(r'\s*(\+?\d{10}|UPI ID:|Bank|Google Pay|PhonePe|Paytm).*', '', person)
            result["to_person"] = person.strip()
            break

    # To UPI and Phone
    to_upi_match = re.search(r"(?:To\s+.*?|UPI ID:)\s*([a-zA-Z0-9.\-_]+@[a-zA-Z0-9.\-_]+)", text, re.IGNORECASE)
    if to_upi_match:
        result["to_upi_id"] = to_upi_match.group(1).strip()

    to_phone_match = re.search(r"(?:To|Paid to):\s*.*?(\+?\d{2}\s?\d{10}|\d{10})", text)
    if to_phone_match:
        result["to_phone_number"] = to_phone_match.group(1).strip()

    return result

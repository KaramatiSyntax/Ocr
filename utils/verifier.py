import pytesseract
import re
import numpy as np
import cv2
from PIL import Image
from PIL.ExifTags import TAGS
import logging
from datetime import datetime, timedelta # Import datetime and timedelta

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Existing advanced_parse_payment_text function (with improved date parsing) ---
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

    amount_match = re.search(r"₹\s*(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)", text)
    if amount_match:
        result["amount"] = float(amount_match.group(1).replace(",", ""))
    else:
        amount_keyword_match = re.search(r"(?:paid|amount|received)\s+.*?(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)", text, re.IGNORECASE | re.DOTALL)
        if amount_keyword_match:
            result["amount"] = float(amount_keyword_match.group(1).replace(",", ""))

    # --- Improved Date and Time Extraction for better parsing ---
    # Attempt to capture full date-time strings first
    # Example: "01:50 pm on 15 May 2025"
    datetime_combined_match = re.search(r"(\d{1,2}:\d{2}(?::\d{2})?\s*[ap]m?)\s+(?:on|at)?\s*(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})", text, re.IGNORECASE)
    if datetime_combined_match:
        result["time"] = datetime_combined_match.group(1).strip()
        result["date"] = datetime_combined_match.group(2).strip()
    else:
        # Fallback to separate date and time
        date_pattern_1 = r"\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4})\b" # e.g., 31 Mar 2024
        date_pattern_2 = r"\b(\d{1,2}/\d{1,2}/\d{2,4})\b" # e.g., 15/05/2025
        date_pattern_3 = r"\b(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})\b"

        date_match = re.search(date_pattern_1, text)
        if not date_match:
            date_match = re.search(date_pattern_2, text)
        if not date_match:
            date_match = re.search(date_pattern_3, text)

        if date_match:
            result["date"] = date_match.group(1).strip()

        time_match = re.search(r"\b(\d{1,2}:\d{2}(?::\d{2})?\s*[AP]M?)\b", text, re.IGNORECASE)
        if time_match:
            result["time"] = time_match.group(1).strip()


    txn_id_patterns = {
        "transaction_id": r"(?:Transaction ID|TID|Txn ID|Trans ID)[:\s]*([A-Za-z0-9-]+)",
        "upi_ref_no": r"(?:UPI Ref No|UPI Ref|Reference No)[:\s]*([0-9]+)",
        "order_id": r"(?:Order ID|Order No)[:\s]*([0-9]+)",
        "utr": r"(?:UTR|UTR No)[:\s]*([0-9]{10,})",
        "google_transaction_id": r"(?:Google transaction ID|Google Txn ID)[:\s]*([A-Za-z0-9-]+)",
        "upi_transaction_id": r"(?:UPI transaction ID|UPI Txn ID)[:\s]*([0-9]+)"
    }

    for key, pattern in txn_id_patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result[key] = match.group(1).strip()

    if not (result["transaction_id"] or result["upi_ref_no"] or result["utr"] or result["order_id"] or result["google_transaction_id"] or result["upi_transaction_id"]):
        generic_txn_match = re.search(r"\b([A-Z0-9]{12,})\b", text)
        if generic_txn_match:
            result["transaction_id"] = generic_txn_match.group(1)

    from_person_match = re.search(r"(?:From|Sender|Debited from|Paid by):\s*([A-Za-z\s.]+?)(?:\s+\+?\d{10}|\s+UPI ID:|Bank)?", text, re.IGNORECASE | re.DOTALL)
    if from_person_match:
        result["from_person"] = from_person_match.group(1).strip()
    elif "From Vijay Kumarvijay" in text:
         result["from_person"] = "Vijay Kumarvijay"

    from_upi_id_match = re.search(r"(?:From\s+.*?|Google Pay\s+)?([a-zA-Z0-9.\-_]+@[a-zA-Z0-9.\-_]+)", text, re.IGNORECASE)
    if from_upi_id_match:
        result["from_upi_id"] = from_upi_id_match.group(1).strip()

    from_phone_match = re.search(r"(?:From|Sender):\s*.*?(\+?\d{2}\s?\d{10}|\d{10})", text, re.IGNORECASE)
    if from_phone_match:
        result["from_phone_number"] = from_phone_match.group(1).strip()

    from_bank_match = re.search(r"(?:From|Debited from)\s+([A-Za-z\s]+?)\s*(?:Bank|P?N?B?\s+\d{4}|HDFC Bank\s*-\s*\d{4})", text, re.IGNORECASE)
    if from_bank_match:
        result["from_bank"] = from_bank_match.group(1).strip()

    to_person_patterns = [
        r"(?:To|Paid to):\s*([A-Za-z\s.]+?)(?:\s+\+?\d{10}|\s+UPI ID:|Bank)?",
        r"Banking Name\s*:\s*([A-Za-z\s]+)",
        r"SANJANA SHUKLA"
    ]

    for pattern in to_person_patterns:
        to_person_match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if to_person_match:
            result["to_person"] = to_person_match.group(1).strip()
            if result["to_person"].upper() == "SANJANA SHUKLA":
                result["to_person"] = "SANJANA SHUKLA"
            break

    to_upi_id_match = re.search(r"(?:To\s+.*?|UPI ID:)\s*([a-zA-Z0-9.\-_]+@[a-zA-Z0-9.\-_]+)", text, re.IGNORECASE)
    if to_upi_id_match:
        result["to_upi_id"] = to_upi_id_match.group(1).strip()

    to_phone_match = re.search(r"(?:To|Paid to):\s*.*?(\+?\d{2}\s?\d{10}|\d{10})", text, re.IGNORECASE)
    if to_phone_match:
        result["to_phone_number"] = to_phone_match.group(1).strip()

    return result

# --- Existing helper functions (verify_logo, detect_photoshop, detect_color_status) ---
def verify_logo(image):
    try:
        screenshot = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        logo = cv2.imread('static/upi_logo.png')
        if logo is None:
            logging.warning("UPI logo file not found at 'static/upi_logo.png'. Logo verification skipped.")
            return False
        result = cv2.matchTemplate(screenshot, logo, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)
        logging.info(f"Logo match confidence: {max_val}")
        return max_val > 0.7
    except Exception as e:
        logging.error(f"Error during logo verification: {e}")
        return False

def detect_photoshop(image):
    try:
        exif_data = image._getexif()
        if not exif_data:
            logging.info("No EXIF data found. Could be an indication of editing or simply original photo.")
            return False

        for tag_id, value in exif_data.items():
            tag = TAGS.get(tag_id, tag_id)
            if tag in ['Software', 'ProcessingSoftware', 'CreatorTool']:
                if 'Adobe' in str(value) or 'Photoshop' in str(value) or 'GIMP' in str(value) or 'Fotor' in str(value):
                    logging.warning(f"Photoshop/Editing software '{value}' detected in EXIF data.")
                    return True
        logging.info("No suspicious editing software detected in EXIF data.")
        return False
    except Exception as e:
        logging.error(f"Error during Photoshop detection: {e}")
        return False

def detect_color_status(image):
    try:
        img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        img_hsv = cv2.cvtColor(img_cv, cv2.COLOR_BGR2HSV)
        color_ranges = {
            "Success": ((40, 50, 50), (80, 255, 255)),
            "Failed": ((0, 100, 100), (10, 255, 255)),
            "Pending": ((20, 100, 100), (40, 255, 255))
        }
        detected = []
        for status, (lower, upper) in color_ranges.items():
            mask = cv2.inRange(img_hsv, np.array(lower), np.array(upper))
            coverage = cv2.countNonZero(mask) / (img_hsv.shape[0] * img_hsv.shape[1])
            if coverage > 0.001:
                detected.append(status)
        return detected or ["Unknown"]
    except Exception as e:
        logging.error(f"Error during color status detection: {e}")
        return ["Error"]


# --- Modified determine_verification_status function ---
def determine_verification_status(extracted_data):
    """
    Determines the overall verification status based on extracted payment details.
    Includes checks for 'paid_to' being 'VINAYAK KUMAR SHUKLA' and date/time within 24 hours.
    """
    is_verified = True
    reasons_false = []
    target_paid_to = "VINAYAK KUMAR SHUKLA"

    logging.info(f"Starting verification for data: {extracted_data}")

    # Criteria 1: Successful Status Detected
    if extracted_data.get("status") not in ["Success", "Completed", "Paid Successfully"]:
        is_verified = False
        reasons_false.append(f"Status is not 'Success' or recognized as successful. Detected: {extracted_data.get('status')}")
        logging.info(f"Verification: Failed due to status: {extracted_data.get('status')}")

    # Criteria 2: Amount Detected
    if extracted_data.get("amount") is None or not isinstance(extracted_data.get("amount"), (int, float)):
        is_verified = False
        reasons_false.append("Amount could not be detected or is invalid.")
        logging.info("Verification: Failed because amount not detected.")

    # Criteria 3: Transaction/Reference ID Detected
    if not (extracted_data.get("transaction_id") or
            extracted_data.get("upi_ref_no") or
            extracted_data.get("order_id") or
            extracted_data.get("utr") or
            extracted_data.get("google_transaction_id") or
            extracted_data.get("upi_transaction_id")):
        is_verified = False
        reasons_false.append("No valid transaction/reference ID found.")
        logging.info("Verification: Failed because no transaction ID found.")

    # Criteria 4: Sender and Receiver Information (at least one for each side)
    sender_info_present = (extracted_data.get("from_person") or
                           extracted_data.get("from_upi_id") or
                           extracted_data.get("from_phone_number"))
    receiver_info_present = (extracted_data.get("to_person") or
                             extracted_data.get("to_upi_id") or
                             extracted_data.get("to_phone_number"))

    if not sender_info_present:
        is_verified = False
        reasons_false.append("Sender information (person, UPI ID, or phone) is missing.")
        logging.info("Verification: Failed because sender info missing.")

    if not receiver_info_present:
        is_verified = False
        reasons_false.append("Receiver information (person, UPI ID, or phone) is missing.")
        logging.info("Verification: Failed because receiver info missing.")

    # --- Criteria for Paid-to must be VINAYAK KUMAR SHUKLA ---
    detected_to_person = extracted_data.get("to_person")
    if detected_to_person:
        if detected_to_person.strip().upper() != target_paid_to.strip().upper():
            is_verified = False
            reasons_false.append(f"Paid-to person does not match '{target_paid_to}'. Detected: '{detected_to_person}'.")
            logging.warning(f"Verification: Failed because 'Paid-to' is not '{target_paid_to}'.")
        else:
            logging.info(f"Verification: 'Paid-to' person matches '{target_paid_to}'.")
    else:
        is_verified = False
        reasons_false.append("Paid-to person could not be detected.")
        logging.warning("Verification: Failed because 'Paid-to' person not detected.")


    # Criteria 5: Date and Time Detected
    extracted_date_str = extracted_data.get("date")
    extracted_time_str = extracted_data.get("time")

    if not extracted_date_str:
        is_verified = False
        reasons_false.append("Date could not be detected.")
        logging.info("Verification: Failed because date not detected.")
    if not extracted_time_str:
        is_verified = False
        reasons_false.append("Time could not be detected.")
        logging.info("Verification: Failed because time not detected.")

    # --- NEW CRITERIA: Date and Time not older than 24 hours ---
    if extracted_date_str and extracted_time_str:
        try:
            # Try to parse the combined datetime
            # Handle different date formats
            dt_formats = [
                "%d %b %Y %I:%M %p",  # 31 Mar 2024 01:58 PM
                "%d %b %Y %I:%M%p",   # 31 Mar 2024 01:58PM
                "%d %B %Y %I:%M %p",  # 15 May 2025 01:50 PM
                "%d/%m/%Y %I:%M %p",  # 20/06/2025 01:50 PM (if applicable)
                "%d %b %Y %H:%M",     # 31 Mar 2024 13:58 (24-hour)
                "%d %B %Y %H:%M"
            ]

            parsed_dt = None
            # Combine date and time for parsing
            full_datetime_str = f"{extracted_date_str} {extracted_time_str}"

            for fmt in dt_formats:
                try:
                    parsed_dt = datetime.strptime(full_datetime_str, fmt)
                    break
                except ValueError:
                    continue

            if parsed_dt:
                current_time = datetime.now() # Get current time for comparison
                time_difference = current_time - parsed_dt
                max_allowed_difference = timedelta(hours=24)

                if time_difference < timedelta(minutes=-5) : # Allow a small future margin (e.g., 5 minutes)
                    is_verified = False
                    reasons_false.append(f"Screenshot date/time is in the future. Detected: {parsed_dt.strftime('%Y-%m-%d %H:%M:%S')}")
                    logging.warning(f"Verification: Failed. Screenshot is in the future. Diff: {time_difference}")
                elif time_difference > max_allowed_difference:
                    is_verified = False
                    reasons_false.append(f"Screenshot is older than 24 hours. Detected: {parsed_dt.strftime('%Y-%m-%d %H:%M:%S')}, Current: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
                    logging.warning(f"Verification: Failed. Screenshot older than 24 hours. Diff: {time_difference}")
                else:
                    logging.info(f"Verification: Screenshot date/time within 24 hours. Diff: {time_difference}")
            else:
                is_verified = False
                reasons_false.append("Could not parse extracted date and time into a comparable format.")
                logging.warning(f"Verification: Failed. Date/Time parsing failed for '{full_datetime_str}'.")
        except Exception as e:
            is_verified = False
            reasons_false.append(f"Error during date/time comparison: {e}")
            logging.error(f"Error in date/time comparison: {e}")
    elif extracted_date_str or extracted_time_str: # If one is found but not the other
        is_verified = False
        reasons_false.append("Only partial date or time information detected, cannot verify recency.")
        logging.warning("Verification: Failed. Partial date/time info.")

    # Criteria 6: Photoshop Detected (Strong negative impact)
    if extracted_data.get("photoshop_detected", False):
        is_verified = False
        reasons_false.append("Potential Photoshop manipulation detected.")
        logging.warning("Verification: Failed due to Photoshop detection.")

    # Criteria 8: Color Status Matches Text Status (Consistency check)
    text_status = extracted_data.get("status")
    color_statuses = extracted_data.get("color_status", [])

    if text_status == "Success" and "Success" not in color_statuses:
        is_verified = False
        reasons_false.append("Text status 'Success' but no matching green color detected.")
        logging.warning("Verification: Failed due to text-color status mismatch (Success).")
    elif text_status == "Failed" and "Failed" not in color_statuses and "Unknown" not in color_statuses:
        is_verified = False
        reasons_false.append("Text status 'Failed' but no matching red color detected.")
        logging.warning("Verification: Failed due to text-color status mismatch (Failed).")

    return {
        "verified": is_verified,
        "reasons_for_false": reasons_false if not is_verified else []
    }

# --- Other helper functions (extract_payment_info) ---
def extract_payment_info(image):
    text = pytesseract.image_to_string(image)
    logging.info(f"OCR extracted text:\n{text[:500]}...")
    return advanced_parse_payment_text(text)
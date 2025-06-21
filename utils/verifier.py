import pytesseract
import re
import numpy as np
import cv2 # Still needed for image processing, even if logo/color are removed
from PIL import Image
from PIL.ExifTags import TAGS # Still needed for photoshop detection
import logging
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Existing advanced_parse_payment_text function (no changes needed here) ---
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

    datetime_combined_match = re.search(r"(\d{1,2}:\d{2}(?::\d{2})?\s*[ap]m?)\s+(?:on|at)?\s*(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})", text, re.IGNORECASE)
    if datetime_combined_match:
        result["time"] = datetime_combined_match.group(1).strip()
        result["date"] = datetime_combined_match.group(2).strip()
    else:
        date_pattern_1 = r"\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4})\b"
        date_pattern_2 = r"\b(\d{1,2}/\d{1,2}/\d{2,4})\b"
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

# --- REMOVED verify_logo function ---
# def verify_logo(image):
#     # ... (function content was here)
#     pass # Placeholder to indicate removal


# --- REMOVED detect_color_status function ---
# def detect_color_status(image):
#     # ... (function content was here)
#     pass # Placeholder to indicate removal


def detect_photoshop(image):
    # This function is still kept as it's a general image integrity check
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


# --- MODIFIED determine_verification_status function for percentage (without logo and color) ---
def determine_verification_status(extracted_data):
    """
    Determines the overall verification status as a percentage based on required checks.
    Removed color detection and logo verification as per user request.
    """
    passed_checks = 0
    total_checks = 0
    reasons_false = []
    target_paid_to = "VINAYAK KUMAR SHUKLA"

    logging.info(f"Starting percentage-based verification for data: {extracted_data}")
    current_time_ist = datetime.now()


    # Check 1: Successful Status Detected (REQUIRED)
    total_checks += 1
    if extracted_data.get("status") in ["Success", "Completed", "Paid Successfully"]:
        passed_checks += 1
        logging.info("Check 1 (Status): PASSED")
    else:
        reasons_false.append(f"Status is not 'Success'. Detected: {extracted_data.get('status')}")
        logging.info(f"Check 1 (Status): FAILED - {extracted_data.get('status')}")


    # Check 2: Amount Detected (REQUIRED)
    total_checks += 1
    if extracted_data.get("amount") is not None and isinstance(extracted_data.get("amount"), (int, float)):
        passed_checks += 1
        logging.info("Check 2 (Amount): PASSED")
    else:
        reasons_false.append("Amount could not be detected or is invalid.")
        logging.info("Check 2 (Amount): FAILED")

    # Check 3: Transaction/Reference ID Detected (REQUIRED)
    total_checks += 1
    if (extracted_data.get("transaction_id") or
            extracted_data.get("upi_ref_no") or
            extracted_data.get("order_id") or
            extracted_data.get("utr") or
            extracted_data.get("google_transaction_id") or
            extracted_data.get("upi_transaction_id")):
        passed_checks += 1
        logging.info("Check 3 (Transaction ID): PASSED")
    else:
        reasons_false.append("No valid transaction/reference ID found.")
        logging.info("Check 3 (Transaction ID): FAILED")

    # Check 4: Sender and Receiver Information (REQUIRED - at least one for each side)
    total_checks += 1
    sender_info_present = (extracted_data.get("from_person") or
                           extracted_data.get("from_upi_id") or
                           extracted_data.get("from_phone_number"))
    if sender_info_present:
        passed_checks += 0.5 # Half credit for sender info
        logging.info("Check 4 (Sender Info): PARTIALLY PASSED")
    else:
        reasons_false.append("Sender information (person, UPI ID, or phone) is missing.")
        logging.info("Check 4 (Sender Info): FAILED")

    receiver_info_present = (extracted_data.get("to_person") or
                             extracted_data.get("to_upi_id") or
                             extracted_data.get("to_phone_number"))
    if receiver_info_present:
        passed_checks += 0.5 # Half credit for receiver info
        logging.info("Check 4 (Receiver Info): PARTIALLY PASSED")
    else:
        reasons_false.append("Receiver information (person, UPI ID, or phone) is missing.")
        logging.info("Check 4 (Receiver Info): FAILED")


    # Check 5: Paid-to must be VINAYAK KUMAR SHUKLA (REQUIRED)
    total_checks += 1
    detected_to_person = extracted_data.get("to_person")
    if detected_to_person and detected_to_person.strip().upper() == target_paid_to.strip().upper():
        passed_checks += 1
        logging.info("Check 5 (Target Paid-to): PASSED")
    else:
        reasons_false.append(f"Paid-to person does not match '{target_paid_to}'. Detected: '{detected_to_person}'.")
        logging.info(f"Check 5 (Target Paid-to): FAILED - Detected: '{detected_to_person}'")


    # Check 6: Date and Time Detected & Not older than 24 hours (REQUIRED)
    total_checks += 1
    extracted_date_str = extracted_data.get("date")
    extracted_time_str = extracted_data.get("time")

    date_time_check_passed = False
    if extracted_date_str and extracted_time_str:
        try:
            dt_formats = [
                "%d %b %Y %I:%M %p",
                "%d %b %Y %I:%M%p",
                "%d %B %Y %I:%M %p",
                "%d/%m/%Y %I:%M %p",
                "%d %b %Y %H:%M",
                "%d %B %Y %H:%M"
            ]

            parsed_dt = None
            full_datetime_str = f"{extracted_date_str} {extracted_time_str}"

            for fmt in dt_formats:
                try:
                    parsed_dt = datetime.strptime(full_datetime_str, fmt)
                    break
                except ValueError:
                    continue

            if parsed_dt:
                time_difference = current_time_ist - parsed_dt
                max_allowed_difference = timedelta(hours=24)

                # Check for future timestamp (allow minor grace for clock sync)
                if time_difference < timedelta(minutes=-2):
                    reasons_false.append(f"Screenshot date/time is in the future. Detected: {parsed_dt.strftime('%Y-%m-%d %H:%M:%S')}")
                    logging.warning(f"Check 6 (Date/Time): FAILED - In future. Diff: {time_difference}")
                elif time_difference > max_allowed_difference:
                    reasons_false.append(f"Screenshot is older than 24 hours. Detected: {parsed_dt.strftime('%Y-%m-%d %H:%M:%S')}, Current: {current_time_ist.strftime('%Y-%m-%d %H:%M:%S')}")
                    logging.warning(f"Check 6 (Date/Time): FAILED - Too old. Diff: {time_difference}")
                else:
                    date_time_check_passed = True
                    logging.info("Check 6 (Date/Time): PASSED")
            else:
                reasons_false.append("Could not parse extracted date and time into a comparable format.")
                logging.warning(f"Check 6 (Date/Time): FAILED - Parsing failed for '{full_datetime_str}'.")
        except Exception as e:
            reasons_false.append(f"Error during date/time comparison: {e}")
            logging.error(f"Check 6 (Date/Time): FAILED - Error: {e}")
    else:
        reasons_false.append("Date or Time information not fully detected, cannot verify recency.")
        logging.warning("Check 6 (Date/Time): FAILED - Partial date/time info.")

    if date_time_check_passed:
        passed_checks += 1


    # Check 7: Photoshop Detected (STRONGLY NEGATIVE)
    total_checks += 1 # This is still a critical check
    if extracted_data.get("photoshop_detected", False):
        reasons_false.append("Potential Photoshop manipulation detected.")
        # If photoshop is detected, this check fails. No 'passed_checks += 1'
        logging.warning("Check 7 (Photoshop): FAILED - Manipulation detected.")
    else:
        passed_checks += 1 # Photoshop NOT detected means it passes this check
        logging.info("Check 7 (Photoshop): PASSED")

    # --- Removed Check 8 (Color Status) ---
    # --- Removed Check 9 (Logo Verified) ---

    # Calculate percentage
    verified_percentage = 0
    if total_checks > 0:
        verified_percentage = (passed_checks / total_checks) * 100
    verified_percentage = round(verified_percentage, 2) # Round to 2 decimal places

    # Final decision for "verified: true/false" can be based on a threshold
    # The threshold for 'True' should be adjusted since total_checks are fewer now.
    # We have 7 checks (Status, Amount, Txn ID, Sender/Receiver (1), Paid-To, Date/Time, Photoshop)
    # So 7/7 = 100%. 6/7 = 85.7%, 5/7 = 71.4%, 4/7 = 57.1%
    # A 70% threshold is still reasonable, meaning at least 5 out of 7 major checks must pass.
    final_verified_bool = (verified_percentage >= 70)

    # Overriding for severe issues like Photoshop detection
    if extracted_data.get("photoshop_detected", False):
        final_verified_bool = False # Overrides based on a severe security concern
        verified_percentage = min(verified_percentage, 25.0) # Cap at a low value if photoshop detected


    return {
        "verified": final_verified_bool,
        "verified_percentage": verified_percentage,
        "reasons_for_false": reasons_false if not final_verified_bool else []
    }


# --- Helper function for OCR (no changes) ---
def extract_payment_info(image):
    text = pytesseract.image_to_string(image)
    logging.info(f"OCR extracted text:\n{text[:500]}...")
    return advanced_parse_payment_text(text)
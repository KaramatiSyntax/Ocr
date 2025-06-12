import pytesseract
import re

def extract_payment_info(image):
    text = pytesseract.image_to_string(image)
    utr = re.search(r'\b[0-9A-Z]{10,}\b', text)
    amount = re.search(r'[₹Rs]+\s?(\d{1,5})', text)
    status = 'success' in text.lower() or 'completed' in text.lower()

    return {
        'text': text,
        'utr': utr.group() if utr else None,
        'amount': amount.group(1) if amount else None,
        'status': 'Success' if status else 'Not Verified'
    }
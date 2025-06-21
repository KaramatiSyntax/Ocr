from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from utils.verifier import (
    extract_payment_info,
    verify_logo,
    detect_photoshop,
    detect_color_status,
    determine_verification_status # Import the new function
)
from PIL import Image
import logging

# Configure logging for app.py as well if needed
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


app = Flask(__name__)
CORS(app, origins=["https://turraniesports.vercel.app", "http://localhost:3000"])

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/verify-payment', methods=['POST'])
def verify_payment():
    if 'screenshot' not in request.files:
        logging.error("No file uploaded.")
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['screenshot']
    try:
        image = Image.open(file.stream)

        # 1. Extract raw payment information
        result = extract_payment_info(image)

        # 2. Perform image-based checks
        result['logo_verified'] = verify_logo(image)
        result['photoshop_detected'] = detect_photoshop(image)
        result['color_status'] = detect_color_status(image)

        # 3. Determine overall verification status
        verification_output = determine_verification_status(result)
        result['verified'] = verification_output['verified']
        if not result['verified']:
            result['reasons_for_false'] = verification_output['reasons_for_false']

        logging.info(f"Verification process completed. Verified: {result['verified']}")
        return jsonify(result)

    except Exception as e:
        logging.exception("Failed to process image") # Logs the full traceback
        return jsonify({'error': 'Failed to process image', 'details': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
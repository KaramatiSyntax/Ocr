from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from utils.verifier import (
    extract_payment_info,
    # REMOVED verify_logo,
    detect_photoshop, # Keep this one as Photoshop detection is still active
    # REMOVED detect_color_status,
    determine_verification_status
)
from PIL import Image
import logging

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

        # 2. Perform image-based checks (Only Photoshop remains)
        # REMOVED result['logo_verified'] = verify_logo(image)
        result['photoshop_detected'] = detect_photoshop(image)
        # REMOVED result['color_status'] = detect_color_status(image)
        
        # Ensure 'color_status' and 'logo_verified' keys are not left uninitialized
        # by simply setting them to None or False if they aren't populated elsewhere.
        # This keeps the 'extracted_data' consistent for determine_verification_status
        # if it somehow tries to access them, though the modified one won't.
        # For a clean approach, ensure determine_verification_status doesn't rely on them.
        # The current determine_verification_status already uses .get() which is safe.
        # So no explicit setting needed here.

        # 3. Determine overall verification status
        verification_output = determine_verification_status(result)

        # Update the main result dictionary with verification details
        result['verified'] = verification_output['verified']
        result['verified_percentage'] = verification_output['verified_percentage']
        if not result['verified']:
            result['reasons_for_false'] = verification_output['reasons_for_false']
        else:
            # If verified is True, ensure reasons_for_false is absent or empty
            if 'reasons_for_false' in result:
                del result['reasons_for_false']


        logging.info(f"Verification process completed. Verified (bool): {result['verified']}, Percentage: {result['verified_percentage']}%")
        return jsonify(result)

    except Exception as e:
        logging.exception("Failed to process image")
        return jsonify({'error': 'Failed to process image', 'details': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
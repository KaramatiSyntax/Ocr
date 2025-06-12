from flask import Flask, request, jsonify, render_template
from utils.ocr import extract_payment_info
from utils.image_checks import verify_logo, detect_photoshop
from PIL import Image

app = Flask(__name__)

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/verify-payment', methods=['POST'])
def verify_payment():
    if 'screenshot' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['screenshot']
    try:
        image = Image.open(file.stream)
        result = extract_payment_info(image)
        logo_result = verify_logo(image)
        photoshop_result = detect_photoshop(image)

        result['logo_verified'] = logo_result
        result['photoshop_detected'] = photoshop_result

        return jsonify(result)
    except Exception as e:
        return jsonify({'error': 'Failed to process image', 'details': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
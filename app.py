from flask import Flask, request, jsonify, render_template
from utils.verifier import extract_payment_info, verify_logo, detect_photoshop
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
        result['logo_verified'] = verify_logo(image)
        result['photoshop_detected'] = detect_photoshop(image)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': 'Failed to process image', 'details': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)

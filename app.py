from flask import Flask, request, render_template, jsonify
from PIL import Image
from utils.verifier import analyze_payment_image

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
        result = analyze_payment_image(image)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': 'Failed to process image', 'details': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
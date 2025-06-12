# Turrani OCR Payment Verification API

## 📦 Features
- Extract UTR, amount, status using OCR
- Detect Photoshop or edited screenshots (basic)
- Logo verification system (placeholder)

## 🚀 Deployment on Render
1. Push this folder to GitHub.
2. Go to https://render.com > New Web Service.
3. Choose your GitHub repo.
4. Add Python 3.10, and `python app.py` as start command.
5. Done.

## 🧪 Test locally
```bash
pip install -r requirements.txt
python app.py
```
Upload an image to `/verify-payment` via form or API.
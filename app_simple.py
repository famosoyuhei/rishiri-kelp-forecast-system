#!/usr/bin/env python3
"""
Simple test version for Railway deployment debugging
"""
import os
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return {'message': 'Rishiri Kelp Forecast System - Test Version', 'status': 'ok'}

@app.route('/health')
def health():
    return {'status': 'healthy', 'version': '1.0.0'}, 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    print(f"Starting server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
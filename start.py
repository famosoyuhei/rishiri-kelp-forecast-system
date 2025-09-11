#!/usr/bin/env python3
"""
Railway deployment startup script
"""
import os
import sys
from flask import Flask

# Create Flask app
app = Flask(__name__)

@app.route('/')
def home():
    return {'message': 'Rishiri Kelp Forecast System - Test Version', 'status': 'ok'}

@app.route('/health')
def health():
    return {'status': 'healthy', 'version': '1.0.0'}, 200

@app.route('/test')
def test():
    return {'test': 'working', 'port': os.environ.get('PORT', 'not_set')}, 200

# Simple startup function
def main():
    port = int(os.environ.get('PORT', 8000))
    print(f"Starting Rishiri Kelp Forecast System on port {port}", file=sys.stdout)
    print(f"Environment PORT: {os.environ.get('PORT', 'NOT SET')}", file=sys.stdout)
    
    app.run(
        host='0.0.0.0', 
        port=port, 
        debug=False,
        threaded=True
    )

if __name__ == '__main__':
    main()
"""
Simplified WSGI entry point for Railway deployment
"""
import os
from start import app

# Health check endpoint
@app.route('/health')
def health():
    return {'status': 'healthy', 'version': '1.0.0'}, 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
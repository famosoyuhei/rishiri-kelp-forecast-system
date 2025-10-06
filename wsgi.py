"""
WSGI entry point for Render deployment
"""
import os
from konbu_flask_final import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)

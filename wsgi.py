"""
WSGI entry point for Render / gunicorn deployment.

This module is imported once per gunicorn worker.  Background threads that
should run per-process (e.g. nightly amedas collection) are started here
rather than at start.py module level, so that:
  - Tests that import start.py don't accidentally start threads
  - The thread is always started when the web process runs
"""
import os
from start import app, _start_background_threads

# Start nightly amedas collection thread.  Daemon=True so it never blocks
# gunicorn worker shutdown.
_start_background_threads()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)

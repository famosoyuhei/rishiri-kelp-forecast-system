# Railway-compatible Dockerfile for Rishiri Kelp Forecast System
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories and set permissions
RUN mkdir -p offline_cache charts backups &&     chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port (Railway will set this via environment variable)
EXPOSE 8000

# Start the application
CMD ["python", "start.py"]

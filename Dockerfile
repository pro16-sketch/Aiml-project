FROM python:3.10-slim

# Install system dependencies for OpenCV and other media processing libraries
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create uploads, temp_outputs, and outputs folders to ensure they exist
RUN mkdir -p uploads temp_outputs outputs

# Expose port
EXPOSE 5001

# Run the app with gunicorn, binding dynamically to $PORT with a fallback to 5001
CMD gunicorn --workers 1 --threads 4 --bind 0.0.0.0:${PORT:-5001} app:app

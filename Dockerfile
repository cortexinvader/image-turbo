FROM python:3.10-slim

# Install Chromium and required system libraries
RUN apt-get update && apt-get install -y \
    chromium \
    wget \
    gnupg \
    unzip \
    fonts-liberation \
    libnss3 \
    libxss1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables for Chromium
ENV CHROME_BIN=/usr/bin/chromium
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your app code
COPY . .

# Expose the port
EXPOSE 10000

# Start the Flask app
CMD ["gunicorn", "-b", "0.0.0.0:10000", "app:app"]

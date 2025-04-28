# Use official Python slim image
FROM python:3.8-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libappindicator3-1 \
    libx11-xcb1 \
    libxtst6 \
    xdg-utils \
    chromium \
    chromium-driver \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables for Selenium
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_BIN=/usr/bin/chromedriver

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . /app

# Set working directory
WORKDIR /app

# Expose the port Flask uses
EXPOSE 5000

# Run the Flask app using gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]

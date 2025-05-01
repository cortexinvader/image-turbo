# Use Python 3.9 slim as base image to keep the image size smaller
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies including Chrome and its dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg2 \
    apt-transport-https \
    ca-certificates \
    curl \
    unzip \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Chrome Driver
RUN CHROME_DRIVER_VERSION=`curl -sS https://chromedriver.storage.googleapis.com/LATEST_RELEASE` && \
    wget -O /tmp/chromedriver.zip https://chromedriver.storage.googleapis.com/$CHROME_DRIVER_VERSION/chromedriver_linux64.zip && \
    unzip /tmp/chromedriver.zip -d /usr/bin && \
    rm /tmp/chromedriver.zip && \
    chmod +x /usr/bin/chromedriver

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application
COPY . .

# Add a non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Set environment variables for Chrome
ENV CHROME_BIN=/usr/bin/google-chrome
ENV CHROME_PATH=/usr/lib/google-chrome
ENV PYTHONUNBUFFERED=1

# Command to run tests (adjust as needed based on your test file name)
CMD ["python", "-m", "pytest"]

FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gnupg \
    wget \
    curl \
    unzip \
    fonts-liberation \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set up ChromeDriver - install latest compatible version
RUN CHROMIUM_VERSION=$(chromium --version | awk '{print $2}' | cut -d'.' -f1) \
    && CHROME_DRIVER_VERSION=$(curl -s "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$CHROMIUM_VERSION") \
    && wget -q -O /tmp/chromedriver.zip "https://chromedriver.storage.googleapis.com/$CHROME_DRIVER_VERSION/chromedriver_linux64.zip" \
    && unzip /tmp/chromedriver.zip -d /usr/bin/ \
    && rm /tmp/chromedriver.zip \
    && chmod +x /usr/bin/chromedriver

# Set environment variables for Chrome and ChromeDriver
ENV CHROME_BINARY_PATH="/usr/bin/chromium"
ENV CHROME_DRIVER_PATH="/usr/bin/chromedriver"

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code
COPY . .

# Expose the port
EXPOSE 8080

# Command to run the application with debug output
CMD exec gunicorn --bind 0.0.0.0:$PORT --log-level debug app:app

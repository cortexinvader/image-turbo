FROM python:3.11-slim

ENV CHROME_VERSION=123.0.6312.105

# Install only valid and required packages
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    curl \
    gnupg \
    ca-certificates \
    libnss3 \
    libxss1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libx11-xcb1 \
    fonts-liberation \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Chromium (for Testing) and ChromeDriver
RUN wget https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux/x64/chrome-linux.zip && \
    unzip chrome-linux.zip && \
    mv chrome-linux /opt/chrome && \
    ln -s /opt/chrome/chrome /usr/bin/chromium

RUN wget https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux/x64/chromedriver-linux64.zip && \
    unzip chromedriver-linux64.zip && \
    mv chromedriver-linux64/chromedriver /usr/bin/chromedriver && \
    chmod +x /usr/bin/chromedriver

ENV DISPLAY=:99

WORKDIR /app
COPY requirements.txt .
COPY app.py .

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "app.py"]

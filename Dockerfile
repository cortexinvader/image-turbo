# Use a base Python image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y \
    wget unzip curl gnupg ca-certificates fonts-liberation \
    libnss3 libxss1 libappindicator3-1 libasound2 libatk-bridge2.0-0 libgtk-3-0 libx11-xcb1 \
    chromium chromium-driver \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the app
COPY . .

# Set Chromium binary path as environment variable (optional, for reference)
ENV CHROME_BIN=/usr/bin/chromium

# Run your app (modify as needed)
CMD ["python", "app.py"]

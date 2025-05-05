FROM python:3.10-slim

# Install Chromium and needed dependencies
RUN apt-get update && apt-get install -y \
    chromium \
    wget \
    unzip \
    git \
    ca-certificates \
    fonts-liberation \
    libnss3 \
    libxss1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

# Set Chromium path
ENV CHROME_BIN=/usr/bin/chromium
ENV PYTHONUNBUFFERED=1

# Create app directory
WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Expose port and run app
EXPOSE 10000
CMD ["gunicorn", "-b", "0.0.0.0:10000", "app:app"]

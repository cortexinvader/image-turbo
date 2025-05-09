FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    chromium-driver \
    chromium \
    fonts-liberation \
    wget \
    unzip \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

ENV DISPLAY=:99
RUN which chromium && which chromedriver
WORKDIR /app

COPY requirements.txt .
COPY app.py .

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "app.py"]

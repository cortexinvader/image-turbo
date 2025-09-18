FROM python:3.11-slim

# Production dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    xvfb \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list' \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && apt-get install -y chromium chromium-driver \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Production Python environment
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy production code
COPY . .

# Production environment variables
ENV FLASK_ENV=production \
    PYTHONUNBUFFERED=1 \
    CHROME_BIN=/usr/bin/chromium \
    CHROMEDRIVER_BIN=/usr/bin/chromedriver

# Production user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 10000

# Production health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:10000/health || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:10000", "--workers", "2", "--worker-class", "gevent", "--timeout", "120", "--log-level", "info", "app:app"]

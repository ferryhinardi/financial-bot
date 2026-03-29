FROM python:3.12-slim

WORKDIR /app

# Install system dependencies (poppler-utils for pdf2image)
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY bot.py .
COPY config.py .
COPY excel_manager.py .
COPY onboarding.py .
COPY create_financial_tracker.py .

# Generate fresh Excel if not mounted
RUN python create_financial_tracker.py

# Data volume for Excel file and state
VOLUME ["/app/data"]

# Run the bot
CMD ["python", "bot.py"]

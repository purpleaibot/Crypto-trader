FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (if any needed for pandas/numpy)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements from root
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY monitoring_bot/ .

# Run the bot
CMD ["python", "main.py"]

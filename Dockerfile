FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY job_monitor.py .

# Create data directory
RUN mkdir -p data

# Run the monitor
CMD ["python", "job_monitor.py"]

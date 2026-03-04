# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory in container
WORKDIR /app

# Install system dependencies if needed
# RUN apt-get update && apt-get install -y \
#     # Add any system dependencies here if required \
#     && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY bot.py .
COPY .env.example .env.example

# Create a placeholder .env file (will be overridden by volume mount or environment)
RUN touch .env

# Expose any ports if needed (not required for Discord bot)
# EXPOSE 8080

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Health check (optional)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Run the bot
CMD ["python", "bot.py"]
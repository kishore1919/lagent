# Use a slim Python image
FROM python:3.11-slim

# Install system dependencies needed for the tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    iproute2 \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose ports for Agent API and MCP Server
EXPOSE 9000 9001

# Default command (can be overridden in docker-compose)
CMD ["python", "main.py"]

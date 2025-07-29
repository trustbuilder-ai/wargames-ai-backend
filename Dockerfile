# Use Python 3.12 slim image to match pyproject.toml requirement
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy only pyproject.toml first for better caching
COPY pyproject.toml .

# Create empty README.md and minimal src structure to satisfy hatchling
RUN touch README.md && \
    mkdir -p src/backend && \
    touch src/backend/__init__.py

# Install pip-tools for better dependency resolution
RUN pip install --no-cache-dir pip-tools

# Generate requirements.txt from pyproject.toml and install dependencies
RUN pip-compile pyproject.toml -o requirements.txt && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables for Cloud Run
ENV PORT=8080
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

# Expose the port
EXPOSE 8080

# Run the FastAPI server with uvicorn
CMD ["uvicorn", "src.backend.server:app", "--host", "0.0.0.0", "--port", "8080"]
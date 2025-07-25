# syntax=docker/dockerfile:1
FROM python:3.11-slim-bullseye

# Set working directory inside container
WORKDIR /app
ENV PYTHONPATH=/app/src

# Install system dependencies
RUN apt-get update && apt-get upgrade -y && apt-get install -y \
    build-essential \
    curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy only dependency-related files (for better Docker caching)
COPY pyproject.toml README.md ./

# Copy the source code before install
COPY src ./src

# Install dependencies + project using setuptools/pyproject.toml
RUN pip install --no-cache-dir ".[dev]"

# Now copy the rest of the project (tests, docs, etc.)
COPY . /app

# Expose Streamlit and FastAPI ports
EXPOSE 8501 8000

# Entrypoint is defined per service in docker-compose
CMD ["uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", "8000"]


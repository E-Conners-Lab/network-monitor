FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for network libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    libssl-dev \
    libsnmp-dev \
    curl \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files and README (required by pyproject.toml)
COPY pyproject.toml README.md ./

# Install Python dependencies (non-editable for Docker)
RUN pip install --no-cache-dir .

# Copy application code
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY scripts/ ./scripts/

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]

FROM python:3.12-slim

# Basic environment
ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System dependencies for psycopg2 and build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies first (better layer caching)
COPY requirements.txt /app/requirements.txt
# If you provide a lock file generated from your conda env (pip freeze), it will be preferred
COPY requirements.lock.txt /app/requirements.lock.txt
RUN pip install --upgrade pip && \
    if [ -f /app/requirements.lock.txt ]; then \
        echo "Installing from requirements.lock.txt" && \
        pip install -r /app/requirements.lock.txt; \
    else \
        echo "Installing from requirements.txt" && \
        pip install -r /app/requirements.txt; \
    fi

# Copy application code
COPY . /app

# Default command (overridden by docker-compose per service)
CMD ["python", "-V"]



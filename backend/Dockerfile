FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libreoffice pandoc \
    && rm -rf /var/lib/apt/lists/*

RUN pip install uv

WORKDIR /app

# Copy dependency file(s) first for caching
COPY pyproject.toml .

# Install dependencies
RUN uv pip install --system --requirements pyproject.toml

# Copy the rest of the backend code (last, so changes here don't bust cache above)
COPY . .

EXPOSE 8001

CMD ["uvicorn", "ewa_main:app", "--host", "0.0.0.0", "--port", "8001"]
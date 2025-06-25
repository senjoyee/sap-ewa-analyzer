FROM python:3.12-slim

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
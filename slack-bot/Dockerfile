FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml README.md ./
COPY app.py handlers.py claude_client.py ./

RUN uv pip install --system --no-cache .

CMD ["python", "app.py"]

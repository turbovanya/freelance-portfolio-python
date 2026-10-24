FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install ".[postgres]"

COPY faq.json ./
RUN useradd --create-home bot && mkdir -p data && chown bot data
USER bot

VOLUME ["/app/data"]
CMD ["lead-bot"]

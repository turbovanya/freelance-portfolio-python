FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install .

COPY profiles ./profiles
RUN useradd --create-home parser && mkdir -p output && chown parser output
USER parser

VOLUME ["/app/output"]
ENTRYPOINT ["price-parser"]
CMD ["run"]

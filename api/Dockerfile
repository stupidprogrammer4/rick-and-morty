FROM python:3.13.16-slim-bookworm@sha256:5024f48ba9441d4b13a95d3945abc6365538e3a31109833367a1923523c6efed
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY api/requirements.lock /tmp/requirements.lock
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/portal-browsers
RUN pip install --no-cache-dir -r /tmp/requirements.lock
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && python -m playwright install --with-deps --only-shell chromium \
    && rm -rf /var/lib/apt/lists/*
COPY packages/contracts /app/packages/contracts
COPY api /app/api
RUN pip install --no-cache-dir --no-deps ./packages/contracts ./api \
    && useradd --create-home --uid 10001 portal
COPY config.yml.sample /app/config.yml
RUN mkdir -p /app/data/media && chown -R portal:portal /app/data
RUN python -m pip check && python -m pip uninstall -y setuptools pip \
    && rm -rf /usr/local/lib/python3.13/ensurepip
USER portal
LABEL org.opencontainers.image.source="https://github.com/stupidprogrammer4/rick-and-morty"
CMD ["uvicorn", "src.apps.api:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]

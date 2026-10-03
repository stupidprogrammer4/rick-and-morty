FROM python:3.13.7-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY api/requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir -r /tmp/requirements.lock
COPY packages/contracts /app/packages/contracts
COPY api /app/api
RUN pip install --no-cache-dir --no-deps ./packages/contracts ./api \
    && useradd --create-home --uid 10001 portal
COPY config.yml.sample /app/config.yml
RUN mkdir -p /app/data && chown portal:portal /app/data
USER portal
CMD ["uvicorn", "src.apps.api:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]

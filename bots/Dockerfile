FROM python:3.13.7-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY bots/requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir -r /tmp/requirements.lock
COPY packages/contracts /app/packages/contracts
COPY bots /app/bots
RUN pip install --no-cache-dir --no-deps ./packages/contracts ./bots \
    && useradd --create-home --uid 10001 portal
USER portal
CMD ["python", "-m", "portal_bots"]

# Dockerfile.c3 — C3 Repayment Engine Container
# Monitors 5 settlement rails; processes SWIFT/FedNow/RTP/SEPA/Buffer signals

FROM python:3.11-slim

LABEL maintainer="LIP Engineering"
LABEL component="c3-repayment-engine"
LABEL description="LIP C3 Repayment Engine — 5-rail settlement monitoring, Redis SETNX idempotency"

WORKDIR /app

RUN pip install --no-cache-dir \
    numpy>=1.26.0 \
    pydantic>=2.5.0 \
    redis>=5.0.0 \
    cryptography>=42.0.0 \
    pyyaml>=6.0 \
    fastapi>=0.110.0 \
    uvicorn[standard]>=0.27.0

# Copy LIP package
COPY lip/ ./lip/
WORKDIR /app/lip
RUN pip install --no-cache-dir -e .
WORKDIR /app

# Non-root user for security
RUN useradd -m -o -u 1000 lipuser && chown -R lipuser:lipuser /app
USER lipuser

# Internal health surface on 8083; the repayment monitor runs in-process.
ENV KAFKA_BOOTSTRAP_SERVERS="kafka:9092" \
    REDIS_URL="redis://redis:6379/0"

EXPOSE 8083

CMD ["uvicorn", "lip.c3_repayment_engine.api:app", "--host", "0.0.0.0", "--port", "8083", "--workers", "1"]

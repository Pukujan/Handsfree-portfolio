FROM python:3.12-slim@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a AS builder

ARG FOSSIL_SHA=b5fd57725c910b149910371964adb35d9280016e
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN git init /tmp/fossil-core \
    && git -C /tmp/fossil-core remote add origin https://github.com/Pukujan/fossil-core.git \
    && git -C /tmp/fossil-core fetch --depth=1 origin "$FOSSIL_SHA" \
    && git -C /tmp/fossil-core checkout --detach FETCH_HEAD \
    && test "$(git -C /tmp/fossil-core rev-parse HEAD)" = "$FOSSIL_SHA"

RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH

COPY services/portfolio-ai /src/services/portfolio-ai
RUN pip install /src/services/portfolio-ai

FROM python:3.12-slim@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a AS runtime

ENV PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FOSSIL_SCHEMA_ROOT=/opt/fossil-schemas \
    PORTFOLIO_PACK_ROOT=/var/lib/handsfree/portfolio-public \
    PORTFOLIO_CACHE_MAX_ENTRIES=256

RUN useradd --create-home --uid 10001 portfolio

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /tmp/fossil-core/schemas /opt/fossil-schemas

USER portfolio
WORKDIR /home/portfolio
EXPOSE 8000

CMD ["uvicorn", "handsfree_portfolio.delivery.api:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]

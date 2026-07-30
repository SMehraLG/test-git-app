FROM python:3.13-slim AS test
WORKDIR /srv
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
COPY src ./src
COPY tests ./tests
ENV UV_SYSTEM_PYTHON=1
RUN uv sync --frozen --extra dev && pytest

FROM python:3.13-slim AS base
WORKDIR /srv
RUN pip install --no-cache-dir uv
COPY --from=test /srv/src ./src
COPY pyproject.toml uv.lock ./
ENV UV_SYSTEM_PYTHON=1
RUN uv sync --frozen --no-dev \
    && groupadd --gid 1001 appuser \
    && useradd --uid 1001 --gid 1001 --no-create-home --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /srv
EXPOSE 8001
USER 1001
CMD ["uvicorn", "connectivity.main:app", "--host", "0.0.0.0", "--port", "8001"]

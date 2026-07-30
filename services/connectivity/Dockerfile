FROM python:3.13-slim-bookworm AS test
WORKDIR /srv
COPY pyproject.toml ./
COPY src ./src
COPY tests ./tests
RUN pip install --no-cache-dir ".[dev]" && pytest

FROM python:3.13-slim-bookworm AS base
WORKDIR /srv
COPY --from=test /srv/src ./src
COPY pyproject.toml ./
RUN pip install --no-cache-dir . \
    && groupadd --gid 1001 appuser \
    && useradd --uid 1001 --gid 1001 --no-create-home --no-log-init --shell /usr/sbin/nologin appuser \
    && chown -R 1001:1001 /srv
EXPOSE 8001
USER 1001
CMD ["uvicorn", "connectivity.main:app", "--host", "0.0.0.0", "--port", "8001"]

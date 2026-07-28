FROM python:3.13-slim AS test
WORKDIR /srv
COPY pyproject.toml ./
COPY src ./src
COPY tests ./tests
RUN pip install --no-cache-dir ".[dev]" && pytest

FROM python:3.13-slim
WORKDIR /srv
COPY --from=test /srv/src ./src
COPY pyproject.toml ./
RUN pip install --no-cache-dir .
EXPOSE 8001
CMD ["uvicorn", "connectivity.main:app", "--host", "0.0.0.0", "--port", "8001"]

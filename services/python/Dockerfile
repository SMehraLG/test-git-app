FROM python:3.13-slim AS test
WORKDIR /srv
COPY pyproject.toml ./
COPY src ./src
COPY tests ./tests
RUN pip install --no-cache-dir ".[dev]" && pytest

FROM python:3.13-slim
WORKDIR /srv
# src/ copied from the test stage — forces the test stage to run and fail-fast on broken tests
COPY --from=test /srv/src ./src
COPY pyproject.toml ./
RUN pip install --no-cache-dir .
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
EXPOSE 8080
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]

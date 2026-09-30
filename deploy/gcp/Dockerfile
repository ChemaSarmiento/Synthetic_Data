FROM ghcr.io/astral-sh/uv:0.12.19 AS uv
FROM python:3.14.4-slim
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --locked --no-dev --no-editable
COPY configs/gcp/aml-pilot.json /app/config.json
COPY deploy/gcp/run_pilot.py deploy/gcp/run_bulk.py /app/
ENV PYTHONUNBUFFERED=1
CMD ["/app/.venv/bin/python", "/app/run_pilot.py"]

FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-cache

COPY main.py pharmacy_functions.py config.json ./

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 5000

CMD ["python", "main.py"]

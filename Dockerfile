FROM python:3.13-slim

WORKDIR /app

RUN pip install --no-cache-dir poetry

COPY pokeapi/poetry.lock pokeapi/pyproject.toml ./

RUN poetry config virtualenvs.create false \
    && poetry install --no-root --no-interaction --no-ansi

COPY pokeapi/ ./pokeapi

ENV PYTHONPATH=/app/pokeapi/src

EXPOSE 8000

CMD ["poetry","run","uvicorn","pokeapi.main:app","--host","0.0.0.0","--port","8000"]
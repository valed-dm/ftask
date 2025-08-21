# Dockerfile (Corrected to include executables)

# Stage 1: Build stage
FROM python:3.12-slim as builder
WORKDIR /app
RUN pip install poetry
COPY poetry.lock pyproject.toml ./
RUN poetry config virtualenvs.create false && \
    poetry install --no-root --without dev

# Stage 2: Final stage
FROM python:3.12-slim
WORKDIR /app

# Install netcat, which is used in the entrypoint script to check the db connection
RUN apt-get update && apt-get install -y netcat-openbsd

# Copy installed libraries AND executables from the builder stage
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy the application code and alembic config
COPY ./app /app/app
COPY ./alembic.ini /app/alembic.ini

# Copy the entrypoint script
COPY ./docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 8000

# Set the entrypoint
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# The command to be executed by the entrypoint script
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

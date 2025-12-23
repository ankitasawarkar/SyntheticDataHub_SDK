# syntax=docker/dockerfile:1
FROM python:3.12-slim

WORKDIR /app

# Install system deps if needed (psycopg2-binary avoids compile step)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

ENV PYTHONUNBUFFERED=1

# Default entrypoint runs the CLI; pass commands/args via `docker run` or compose
ENTRYPOINT ["python", "src/cli.py"]
# No default CMD; provide subcommand like: generate/init_schema/pipeline

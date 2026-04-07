FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency files
COPY ./pyproject.toml /app/pyproject.toml
COPY ./README.md /app/README.md
COPY ./src /app/src
COPY ./uv.lock /app/uv.lock

# Install dependencies
RUN uv sync --frozen --no-dev

# Expose port (adjust as needed)
EXPOSE 8000

# Set the default command
CMD ["uv", "run", "main"]

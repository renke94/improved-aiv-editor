# Improved AIV Editor

A Python project template

## Installation

```bash
pip install improved_aiv_editor
```

## Usage

```python
from improved_aiv_editor import main

main()
```

## Development

This project uses [uv](https://docs.astral.sh/uv/) for dependency management.

```bash
# Install dependencies
uv sync

# Run the project
uv run main

# Run linting
uv run --group lint ruff check
uv run --group lint mypy src

# Run tests
uv run pytest
```

## Docker

This project includes Docker support for easy deployment and development.

### Prerequisites

This project uses a shared S3 infrastructure. Before running the application, start the S3 services:

```bash
# Navigate to S3 infrastructure folder (adjust path as needed)
cd ../s3-infrastructure

# Setup and start S3 services (MinIO)
./setup.sh

# Or manually:
docker network create s3-network
docker-compose up -d
```

### Using Docker Compose (Recommended)

```bash
# Build and run the application
docker-compose up --build

# Run in detached mode
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop the application
docker-compose down
```

### Using Docker directly

```bash
# Build the image
docker build -t improved_aiv_editor .

# Run the container
docker run -p 8000:8000 improved_aiv_editor
```

### Development with Docker

The docker-compose.yml file is configured for development with volume mounts:
- Source code is mounted so changes are reflected without rebuilding
- Environment file (.env) is mounted if it exists

For production deployment, comment out the volume mounts in docker-compose.yml.


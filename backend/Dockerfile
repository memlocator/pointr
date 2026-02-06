FROM python:3.14-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY backend/pyproject.toml backend/uv.lock ./
COPY proto/enrichment.proto ./
COPY proto/recon.proto ./

# Install dependencies
RUN uv sync --frozen

# Generate gRPC code from proto files
RUN uv run python -m grpc_tools.protoc \
    -I. \
    --python_out=. \
    --grpc_python_out=. \
    enrichment.proto

RUN uv run python -m grpc_tools.protoc \
    -I. \
    --python_out=. \
    --grpc_python_out=. \
    recon.proto

# Copy application code
COPY backend/main.py ./

# Expose port
EXPOSE 8000

# Run with hot reload in development
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

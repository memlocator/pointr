FROM python:3.14-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY enrichment/pyproject.toml enrichment/uv.lock ./
COPY proto/enrichment.proto ./

# Install dependencies
RUN uv sync --frozen

# Generate gRPC code from proto file
RUN uv run python -m grpc_tools.protoc \
    -I. \
    --python_out=. \
    --grpc_python_out=. \
    enrichment.proto

# Copy application code
COPY enrichment/main.py ./

# Expose gRPC port
EXPOSE 50051

# Run the gRPC server
CMD ["uv", "run", "python", "main.py"]

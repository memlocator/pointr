FROM python:3.14-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY recon/pyproject.toml recon/uv.lock* ./
COPY proto/recon.proto ./

# Install dependencies
RUN uv sync --frozen || uv sync

# Generate gRPC code from proto file
RUN uv run python -m grpc_tools.protoc \
    -I. \
    --python_out=. \
    --grpc_python_out=. \
    recon.proto

# Copy shared common module
COPY common/ /app/common/

# Copy application code
COPY recon/main.py ./
COPY recon/dev_server.py ./

# Expose gRPC port
EXPOSE 50052

# Run the gRPC server with hot reload
CMD ["uv", "run", "python", "dev_server.py"]

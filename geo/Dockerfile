FROM python:3.14-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY geo/pyproject.toml geo/uv.lock ./
COPY proto/geo.proto ./

# Install dependencies
RUN uv sync --frozen

# Generate gRPC code from proto file
RUN uv run python -m grpc_tools.protoc \
    -I. \
    --python_out=. \
    --grpc_python_out=. \
    geo.proto

# Copy shared common module
COPY common/ /app/common/

# Copy application code
COPY geo/main.py ./
COPY geo/dev_server.py ./

# Expose gRPC port
EXPOSE 50051

# Run the gRPC server with hot reload
CMD ["uv", "run", "python", "dev_server.py"]

FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY recon/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy proto file and generate gRPC code
COPY proto/recon.proto .
RUN python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. recon.proto

# Copy service code
COPY recon/main.py .

# Expose gRPC port
EXPOSE 50052

CMD ["python", "main.py"]

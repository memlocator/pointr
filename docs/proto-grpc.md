# Proto & gRPC

Pointr uses gRPC for internal service communication. The backend talks to the geo and recon services over gRPC. The frontend never speaks gRPC directly — it uses the backend REST API.

## Files

```
proto/
├── geo.proto       # Geo data service (enrichment, custom POIs, areas, routes)
└── recon.proto     # Reconnaissance service

geo/
├── geo_pb2.py          # Generated message classes
└── geo_pb2_grpc.py     # Generated service stubs

backend/
├── geo_pb2.py          # Same, copied/regenerated for backend use
├── geo_pb2_grpc.py
├── recon_pb2.py
└── recon_pb2_grpc.py
```

Each service directory has its own copy of the generated files because they run in separate Python environments (separate Docker containers, separate `uv` venvs).

## Regenerating stubs

Run this after modifying any `.proto` file. You need to regenerate in **both** `geo/` and `backend/` (and `recon/` if you changed `recon.proto`):

```bash
cd geo
uv run python -m grpc_tools.protoc -I../proto --python_out=. --grpc_python_out=. ../proto/geo.proto

cd ../backend
uv run python -m grpc_tools.protoc -I../proto --python_out=. --grpc_python_out=. ../proto/geo.proto
uv run python -m grpc_tools.protoc -I../proto --python_out=. --grpc_python_out=. ../proto/recon.proto
```

If you're running inside Docker, the containers need to be rebuilt after regenerating stubs (the generated files are baked in at build time, not volume-mounted):

```bash
docker compose build geo backend
docker compose up -d geo backend
```

## Adding a field to an existing message

Proto3 is forward-compatible: adding new fields with new field numbers is safe — old clients just ignore them.

1. Open `proto/geo.proto` (or `recon.proto`)
2. Add your field with the **next available field number**:
   ```proto
   message AddCustomPOIRequest {
     ...
     string my_new_field = 9;   // pick the next unused number
   }
   ```
3. Regenerate stubs in all affected directories (see above)
4. Update the service implementation (`geo/main.py`) to read/write the field
5. Update the backend proxy (`backend/main.py`) to pass the field through
6. Update the frontend payload and forms

**Never reuse a field number** — proto uses field numbers for binary encoding. Reusing a number for a different type corrupts data.

## Adding a new RPC method

1. Add the method signature to the `service` block in the proto file:
   ```proto
   service GeoDataService {
     rpc MyNewMethod(MyRequest) returns (MyResponse);
   }
   ```
2. Define the request/response messages
3. Regenerate stubs
4. Implement the method in the servicer class (`geo/main.py` → `class GeoDataServicer`)
5. Add a corresponding REST endpoint in `backend/main.py` that calls the new gRPC method

## Debugging

Check that the service is up and the proto version matches:

```bash
# Verify geo service is reachable
docker compose exec backend python -c "
import grpc
import geo_pb2_grpc, geo_pb2
ch = grpc.insecure_channel('geo:50051')
stub = geo_pb2_grpc.GeoDataServiceStub(ch)
print(stub.Health(geo_pb2.HealthRequest()))
"
```

If you see `StatusCode.UNIMPLEMENTED`, the method exists in the proto but is missing from the servicer implementation.

If you see attribute errors on the generated classes, the stubs are out of sync with the proto — regenerate.

"""OpenShell gRPC stub package.

grpc_tools.protoc generates flat imports (import datamodel_pb2 ...) rather
than package-qualified ones. This __init__ adds the proto directory to
sys.path at import time so the stubs resolve correctly.
"""

import sys
from pathlib import Path

_PROTO_DIR = str(Path(__file__).parent / "proto")
if _PROTO_DIR not in sys.path:
    sys.path.insert(0, _PROTO_DIR)

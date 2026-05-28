#!/usr/bin/env bash
# Vendor OpenShell proto files at the pinned commit.
# Idempotent — running twice is safe.
set -euo pipefail

PINNED_COMMIT="6c7950da900921a24aa65e79c7b522ba12fd7875"
REPO_URL="https://github.com/NVIDIA/OpenShell.git"
VENDOR_DIR="vendor/openshell"

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

echo "Vendoring OpenShell protos at commit ${PINNED_COMMIT:0:8}..."

mkdir -p "$VENDOR_DIR"

# Shallow-clone, checkout pinned commit, extract proto/ tree only.
TMP_DIR="$(mktemp -d)"
trap "rm -rf $TMP_DIR" EXIT

git -C "$TMP_DIR" init -q
git -C "$TMP_DIR" remote add origin "$REPO_URL"
git -C "$TMP_DIR" fetch --depth 1 origin "$PINNED_COMMIT" -q
git -C "$TMP_DIR" checkout -q FETCH_HEAD

if [ ! -d "$TMP_DIR/proto" ]; then
    echo "ERROR: $TMP_DIR/proto not found at pinned commit." >&2
    echo "OpenShell repo layout may have changed. Update PINNED_COMMIT or path." >&2
    exit 1
fi

rm -rf "$VENDOR_DIR/proto"
cp -R "$TMP_DIR/proto" "$VENDOR_DIR/proto"

# Pin file for traceability.
cat > "$VENDOR_DIR/PINNED_COMMIT" <<EOF
commit: $PINNED_COMMIT
date:   $(git -C "$TMP_DIR" log -1 --format=%ci FETCH_HEAD)
source: $REPO_URL
EOF

echo "Vendored to: $VENDOR_DIR/proto"
ls "$VENDOR_DIR/proto"

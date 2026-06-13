#!/bin/bash
set -e

SRC_DIR="$HOME/.ollama/models"
DEST_DIR="build/ollama_models"

echo "Creating destination directories..."
mkdir -p "$DEST_DIR/manifests/registry.ollama.ai/library/phi3"
mkdir -p "$DEST_DIR/blobs"

echo "Copying manifest..."
cp "$SRC_DIR/manifests/registry.ollama.ai/library/phi3/mini" "$DEST_DIR/manifests/registry.ollama.ai/library/phi3/mini"

echo "Copying blobs..."
# Read digests from manifest and copy them
# Config digest:
CONFIG_DIGEST="23291dc44752bac878bf46ab0f2b8daf75c710060f80f1a351151c7be2f5ee0f"
cp "$SRC_DIR/blobs/sha256-$CONFIG_DIGEST" "$DEST_DIR/blobs/sha256-$CONFIG_DIGEST"

# Model digest:
MODEL_DIGEST="633fc5be925f9a484b61d6f9b9a78021eeb462100bd557309f01ba84cac26adf"
cp "$SRC_DIR/blobs/sha256-$MODEL_DIGEST" "$DEST_DIR/blobs/sha256-$MODEL_DIGEST"

# License digest:
LICENSE_DIGEST="fa8235e5b48faca34e3ca98cf4f694ef08bd216d28b58071a1f85b1d50cb814d"
cp "$SRC_DIR/blobs/sha256-$LICENSE_DIGEST" "$DEST_DIR/blobs/sha256-$LICENSE_DIGEST"

# Template digest:
TEMPLATE_DIGEST="542b217f179c7825eeb5bca3c77d2b75ed05bafbd3451d9188891a60a85337c6"
cp "$SRC_DIR/blobs/sha256-$TEMPLATE_DIGEST" "$DEST_DIR/blobs/sha256-$TEMPLATE_DIGEST"

# Params digest:
PARAMS_DIGEST="8dde1baf1db03d318a2ab076ae363318357dff487bdd8c1703a29886611e581f"
cp "$SRC_DIR/blobs/sha256-$PARAMS_DIGEST" "$DEST_DIR/blobs/sha256-$PARAMS_DIGEST"

echo "Successfully copied phi3:mini model files to $DEST_DIR!"

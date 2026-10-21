#!/bin/bash
# UniDocVerse Tauri Desktop Installer Builder
set -euo pipefail
export CI=true

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DASHBOARD_DIR="$PROJECT_ROOT/unidocverse-dashboard"
SERVICE_DIR="$PROJECT_ROOT/unidocverse-service"
INSTALLER_DIR="$PROJECT_ROOT/unidocverse-installer"
TAURI_DIR="$INSTALLER_DIR/src-tauri"
RESOURCES_DIR="$TAURI_DIR/resources"

print_step() { echo -e "${YELLOW}▶ $1${NC}"; }
print_success() { echo -e "${GREEN}✓ $1${NC}"; }
print_error() { echo -e "${RED}✗ $1${NC}"; }

# LITE=1 bash build_desktop_installer_tauri.sh → Lite DMG: no bundled answer model (phi3/Ollama),
# no PaddleOCR, no Windows/Intel Postgres. Keeps the search model + full reranker.
LITE="${LITE:-0}"
BACKEND_DIST="backend-dist"; [ "$LITE" = "1" ] && BACKEND_DIST="backend-dist-lite"
export UDV_LITE="$LITE"
print_info() { echo -e "${BLUE}ℹ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠ $1${NC}"; }

# Ensure Rust environment is sourced
if [ -f "$HOME/.cargo/env" ]; then
    source "$HOME/.cargo/env"
fi

# Ensure macOS Code Signing environment is sourced
CODESIGN_FILE="$INSTALLER_DIR/codesign.env"
if [ -f "$CODESIGN_FILE" ]; then
    print_step "Sourcing codesign.env..."
    source "$CODESIGN_FILE"
    export APPLE_SIGNING_IDENTITY="${DEVELOPER_ID_APPLICATION:-}"
    export APPLE_PASSWORD="${APPLE_APP_PASSWORD:-}"
    print_success "Code signing environment variables exported ✓"
fi

# Clean & Prepare Resources Directory
print_step "Preparing resources directory..."
rm -rf "$RESOURCES_DIR"
mkdir -p "$RESOURCES_DIR"

# 1. Build Angular Dashboard
print_step "Building Angular dashboard..."
cd "$DASHBOARD_DIR"
npm install --loglevel=error
npm run build -- --configuration=production
print_success "Dashboard built ✓"

# 2. Prepare & Build Python Backend
if [ -f "$INSTALLER_DIR/$BACKEND_DIST/unidocverse-backend/unidocverse-backend" ]; then
    print_info "Python backend binary already compiled under $BACKEND_DIST/ ✓ Skipping rebuild."
else
    print_step "Preparing and building Python backend..."
    cd "$SERVICE_DIR"
    [ ! -d "venv-arm64" ] && python3 -m venv venv-arm64
    source venv-arm64/bin/activate
    uv pip install --python venv-arm64/bin/python -r requirements.txt --quiet
    deactivate

    cd "$INSTALLER_DIR"
    python3 scripts/build_backend_venv.py
    print_success "Backend binary compiled ✓"
fi

# Copy backend executable folder to tauri resources
cd "$INSTALLER_DIR"
mkdir -p "$RESOURCES_DIR/backend"
cp -R "$BACKEND_DIST"/unidocverse-backend/. "$RESOURCES_DIR/backend/"
chmod +x "$RESOURCES_DIR/backend/unidocverse-backend" || true

# 3. Copy PostgreSQL binaries
print_step "Packaging database binaries..."
cd "$INSTALLER_DIR"
[ ! -d "postgres-portable/mac-arm64" ] && npm run package:postgres > /dev/null 2>&1

# Copy macOS Postgres binaries
if [ -d "postgres-portable/mac-arm64" ]; then
    mkdir -p "$RESOURCES_DIR/postgres-arm64"
    cp -R postgres-portable/mac-arm64/. "$RESOURCES_DIR/postgres-arm64/"
fi
if [ "$LITE" != "1" ] && [ -d "postgres-portable/mac-x64" ]; then
    mkdir -p "$RESOURCES_DIR/postgres-x64"
    cp -R postgres-portable/mac-x64/. "$RESOURCES_DIR/postgres-x64/"
fi
if [ "$LITE" != "1" ] && [ -d "postgres-portable/win" ]; then
    mkdir -p "$RESOURCES_DIR/postgres-win"
    cp -R postgres-portable/win/. "$RESOURCES_DIR/postgres-win/"
fi
print_success "Database binaries staged ✓"

# 4. Copy Migrations
print_step "Staging database migrations..."
MIGRATIONS_SRC="$SERVICE_DIR/migrations/sql"
if [ -d "$MIGRATIONS_SRC" ]; then
    mkdir -p "$RESOURCES_DIR/migrations/sql"
    cp -R "$MIGRATIONS_SRC"/. "$RESOURCES_DIR/migrations/sql/"
fi
print_success "Migrations staged ✓"

# 5. Copy Models
print_step "Staging AI models..."
MODEL_SRC="$SERVICE_DIR/models/all-mpnet-base-v2"
if [ -d "$MODEL_SRC" ]; then
    mkdir -p "$RESOURCES_DIR/models/all-mpnet-base-v2"
    cp -R "$MODEL_SRC/." "$RESOURCES_DIR/models/all-mpnet-base-v2/"
fi
# Reranker: picks the passages the answer model reads — bundled so search is accurate offline
RERANK_SRC="$SERVICE_DIR/models/bge-reranker-v2-m3"
if [ -f "$RERANK_SRC/model.safetensors" ]; then
    mkdir -p "$RESOURCES_DIR/models/bge-reranker-v2-m3"
    cp -R "$RERANK_SRC/." "$RESOURCES_DIR/models/bge-reranker-v2-m3/"
else
    print_error "Reranker missing at $RERANK_SRC — search accuracy would drop. Copy it there first."
    exit 1
fi
print_success "AI models staged ✓"

# 5.1. Copy Frontend (to allow backend to serve it directly in browser)
print_step "Staging frontend for browser server..."
FRONTEND_SRC="$DASHBOARD_DIR/dist/unidocverse-dashboard/browser"
if [ -d "$FRONTEND_SRC" ]; then
    mkdir -p "$RESOURCES_DIR/frontend"
    cp -R "$FRONTEND_SRC/." "$RESOURCES_DIR/frontend/"
fi
print_success "Frontend staged ✓"

# 5.2. Copy Tesseract OCR (portable)
print_step "Staging Tesseract OCR..."
TESS_SRC="$INSTALLER_DIR/tesseract-portable"
if [ -d "$TESS_SRC" ]; then
    mkdir -p "$RESOURCES_DIR/tesseract"
    cp -R "$TESS_SRC/." "$RESOURCES_DIR/tesseract/"
    chmod +x "$RESOURCES_DIR/tesseract/bin/tesseract" || true
fi
print_success "Tesseract OCR staged ✓"

# 5.3. Copy Ollama + Models (portable)
print_step "Staging Ollama + models..."
OLLAMA_SRC="$INSTALLER_DIR/ollama-portable"; [ "$LITE" = "1" ] && OLLAMA_SRC="/nonexistent-lite-build"   # Lite: no bundled model
if [ -d "$OLLAMA_SRC" ]; then
    mkdir -p "$RESOURCES_DIR/ollama-portable"
    cp -R "$OLLAMA_SRC/." "$RESOURCES_DIR/ollama-portable/"
    chmod +x "$RESOURCES_DIR/ollama-portable/ollama" || true
fi
print_success "Ollama and models staged ✓"

# 5.5. Code Sign Resources (Crucial for macOS Notarization)
if [ -f "${CODESIGN_FILE:-}" ] && [ -n "${DEVELOPER_ID_APPLICATION:-}" ]; then
    print_step "Signing embedded resources for macOS..."
    ENTITLEMENTS="$INSTALLER_DIR/build/entitlements.mac.plist"
    [ ! -f "$ENTITLEMENTS" ] && print_error "Entitlements not found: $ENTITLEMENTS"

    # Sign all loose .dylib and .so files
    print_info "Signing .dylib and .so files..."
    while IFS= read -r -d '' f; do
        codesign --force --timestamp --options runtime \
                 --entitlements "$ENTITLEMENTS" \
                 --sign "$DEVELOPER_ID_APPLICATION" \
                 "$f" 2>&1 | grep -vE "replacing existing|resource fork" || true
    done < <(find "$RESOURCES_DIR" -type f \( -name "*.dylib" -o -name "*.so" \) -print0 2>/dev/null)

    # Sign all Mach-O executables in resource folders
    print_info "Signing Mach-O executable binaries..."
    for dir in "$RESOURCES_DIR/postgres-arm64" "$RESOURCES_DIR/postgres-x64" "$RESOURCES_DIR/backend" "$RESOURCES_DIR/tesseract/bin" "$RESOURCES_DIR/ollama-portable"; do
        if [ -d "$dir" ]; then
            while IFS= read -r -d '' f; do
                if file "$f" 2>/dev/null | grep -qE "Mach-O"; then
                    codesign --force --timestamp --options runtime \
                             --entitlements "$ENTITLEMENTS" \
                             --sign "$DEVELOPER_ID_APPLICATION" \
                             "$f" 2>&1 | grep -vE "replacing existing|resource fork" || true
                fi
            done < <(find "$dir" -type f -print0 2>/dev/null)
        fi
    done

    # Sign native libraries inside Flyway JARs if present
    if [ -d "$RESOURCES_DIR/flyway" ] || [ -d "$RESOURCES_DIR/migrations" ]; then
        print_info "Signing native libraries inside flyway/migration JAR files..."
        python3 - << PYEOF
import os, subprocess, zipfile, shutil, tempfile, sys

RESOURCES  = "$RESOURCES_DIR"
CERT       = "$DEVELOPER_ID_APPLICATION"
ENTITLE    = "$ENTITLEMENTS"

def sign_file(path):
    r = subprocess.run([
        "codesign", "--force", "--timestamp", "--options", "runtime",
        "--entitlements", ENTITLE, "--sign", CERT, path
    ], capture_output=True, text=True)
    return r.returncode == 0

for root, dirs, files in os.walk(RESOURCES):
    for f in files:
        if not f.endswith(".jar"):
            continue
        jar_path = os.path.join(root, f)
        try:
            with zipfile.ZipFile(jar_path, 'r') as z:
                natives = [n for n in z.namelist()
                           if n.endswith(('.jnilib', '.dylib', '.so'))
                           and not n.endswith('/')]
        except Exception:
            continue
        if not natives:
            continue
        print(f"  Processing {f} ({len(natives)} native libs)...")
        tmp = tempfile.mkdtemp()
        try:
            with zipfile.ZipFile(jar_path, 'r') as z:
                z.extractall(tmp)
            signed = 0
            for n in natives:
                lib = os.path.join(tmp, n)
                if os.path.isfile(lib) and sign_file(lib):
                    signed += 1
            with zipfile.ZipFile(jar_path, 'w', zipfile.ZIP_DEFLATED) as zout:
                for dp, _, fns in os.walk(tmp):
                    for fn in fns:
                        if fn == "original.jar":
                            continue
                        fp = os.path.join(dp, fn)
                        zout.write(fp, os.path.relpath(fp, tmp))
            print(f"    ✓ Signed {signed}/{len(natives)} libs, repacked {f}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
PYEOF
    fi

    print_success "Embedded resources successfully signed ✓"
fi

# 5.9. Clear macOS extended attributes (Prevents Tauri xattr failure)
print_step "Clearing extended attributes from staging..."
xattr -cr "$RESOURCES_DIR" 2>/dev/null || true
xattr -cr "$TAURI_DIR" 2>/dev/null || true

# Ensure all staged resources are writable by the owner (prevents Tauri Permission Denied error 13 on rebuilds)
print_step "Ensuring resources are writable by owner..."
chmod -R u+w "$RESOURCES_DIR" 2>/dev/null || true
# Also ensure existing resources in target directories are writable so they can be overwritten
if [ -d "$TAURI_DIR/target" ]; then
    find "$TAURI_DIR/target" -type d -name "resources" -exec chmod -R u+w {} + 2>/dev/null || true
fi


# 6. Run Tauri Build
print_step "Compiling Tauri app package (Universal macOS Binary)..."
cd "$INSTALLER_DIR"
# Unset Apple notarization env vars — we handle notarization ourselves after the build
APPLE_ID_SAVED="${APPLE_ID:-}"
APPLE_PASSWORD_SAVED="${APPLE_APP_PASSWORD:-}"
APPLE_TEAM_ID_SAVED="${APPLE_TEAM_ID:-}"
unset APPLE_ID APPLE_PASSWORD APPLE_APP_PASSWORD APPLE_APP_SPECIFIC_PASSWORD
npx tauri build --target universal-apple-darwin
# Restore for our notarization step
export APPLE_ID="${APPLE_ID_SAVED}"
export APPLE_APP_PASSWORD="${APPLE_PASSWORD_SAVED}"
export APPLE_TEAM_ID="${APPLE_TEAM_ID_SAVED}"
print_success "Tauri build completed ✓"

# 7. Notarize + Staple DMG
DMG_PATH="$TAURI_DIR/target/universal-apple-darwin/release/bundle/dmg/unidocverse_0.1.0_universal.dmg"

if [ ! -f "$DMG_PATH" ]; then
    print_error "DMG not found at expected path: $DMG_PATH"
    exit 1
fi

print_success "DMG created ✓  ($(du -sh "$DMG_PATH" | cut -f1))"

if [ -n "${APPLE_ID:-}" ] && [ -n "${APPLE_APP_PASSWORD:-}" ] && [ -n "${APPLE_TEAM_ID:-}" ]; then
    print_step "Submitting DMG for Apple notarization..."

    # Store credentials (idempotent) — treat credential errors as non-fatal
    STORE_OUT=$(xcrun notarytool store-credentials "notarytool-profile" \
        --apple-id "$APPLE_ID" \
        --team-id "$APPLE_TEAM_ID" \
        --password "$APPLE_APP_PASSWORD" 2>&1) || true
    if echo "$STORE_OUT" | grep -qi "error\|invalid\|incorrect\|401"; then
        print_warning "Notarization credential error — skipping notarization (DMG is built and signed)"
        print_info "Fix: regenerate your App-Specific Password at appleid.apple.com"
    else
        # Submit and wait (typically 2–5 min)
        NOTARY_OUT=$(xcrun notarytool submit "$DMG_PATH" \
            --keychain-profile "notarytool-profile" \
            --wait 2>&1) || true
        echo "$NOTARY_OUT"

        if echo "$NOTARY_OUT" | grep -q "status: Accepted"; then
            print_success "Notarization accepted ✓"

            print_step "Stapling notarization ticket to DMG..."
            xcrun stapler staple "$DMG_PATH" || print_warning "Staple failed — check manually"
            print_success "Ticket stapled ✓"

            print_step "Verifying Gatekeeper acceptance..."
            spctl --assess --type open --context context:primary-signature "$DMG_PATH" 2>&1 && \
                print_success "Gatekeeper: ACCEPTED ✓ — DMG is ready for distribution" || \
                print_warning "Gatekeeper check failed — DMG may still work, check manually"
        else
            print_warning "Notarization not accepted. Check log above for details."
            SUB_ID=$(echo "$NOTARY_OUT" | grep "id:" | head -1 | awk '{print $2}')
            [ -n "$SUB_ID" ] && print_info "Fetch full log: xcrun notarytool log $SUB_ID --keychain-profile notarytool-profile"
        fi
    fi
else
    print_warning "Skipping notarization — APPLE_ID/APPLE_APP_PASSWORD/APPLE_TEAM_ID not set"
    print_info "To notarize: set those env vars (or add to codesign.env) and re-run"
fi

echo ""
echo -e "${GREEN}=================================================${NC}"
echo -e "${GREEN}🎉 UniDocVerse Desktop Installer build complete!${NC}"
echo -e "${GREEN}=================================================${NC}"
echo -e "${BLUE}   DMG: $DMG_PATH${NC}"
echo -e "${BLUE}   App: $TAURI_DIR/target/universal-apple-darwin/release/bundle/macos/unidocverse.app${NC}"

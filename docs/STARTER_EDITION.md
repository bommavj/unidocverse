# UniDocVerse Starter — the very lite macOS build

Starter is the smallest UniDocVerse desktop app: under 2 GB, so it is published as a file on
**GitHub Releases**. It has the same accuracy as the other editions once setup finishes; the large
search reranker is downloaded on first launch instead of being inside the installer.

## Editions

| Edition | Installer | What's inside | Published on |
|---|---|---|---|
| Full | ~4.8 GB | Everything, including a built-in answer model | [unidocverse.com](https://unidocverse.com) |
| Lite | ~2.4 GB | No answer model (uses Ollama or a cloud key), full reranker | [unidocverse.com](https://unidocverse.com) |
| **Starter** | **~0.8 GB** | Lite, with the reranker downloaded on first launch | **GitHub Releases** |
| Docker Lite | image | Same as Lite, for Windows / Mac / Linux | [Docker Hub](https://hub.docker.com/r/bommavj/unidocverse) |

### What Starter contains

| Part | Size (unpacked) | Notes |
|---|---|---|
| Backend (Lite) | 1.1 GB | FastAPI service; no PaddleOCR, no bundled answer model |
| Search model `all-mpnet-base-v2` | 419 MB | Embeddings for search |
| PostgreSQL + pgvector | 90 MB | Local database |
| SearxNG | 131 MB | Private web search (off until an admin turns it on) |
| **Not included:** reranker `bge-reranker-v2-m3` | 2.1 GB | Downloaded on first launch, checksum verified |

About 1.75 GB unpacked, ~0.8 GB as a compressed DMG.

## Requirements

- macOS 14 or later on Apple Silicon (M1 or newer), 16 GB memory
- [Ollama](https://ollama.com) with `ollama pull mistral:7b`, or a cloud model key added in **Integrations**
- Optional, for forms and charts: `ollama pull gemma4`
- About 3 GB free disk for the app and the downloaded search model

## First launch

1. Open the DMG and drag UniDocVerse to Applications.
2. Start UniDocVerse. The Home page shows **"Finishing setup: downloading search model (2.1 GB)"**.
   - The file comes from the UniDocVerse download server only, and is checked against its SHA-256.
   - A broken download resumes where it stopped.
   - Until it finishes, search still works without reranking, and answers say so.
3. Sign in, upload documents, and ask questions in **Research**.

---

## Building and releasing Starter (maintainers)

### 1. One-time setup

- Apple Developer ID certificate and a notarization profile:
  `xcrun notarytool store-credentials unidocverse-notarize`
- GitHub CLI signed in: `gh auth login`
- `rclone` remote `r2:` for the Cloudflare R2 bucket (hosts the reranker for first-launch download)
- Upload the reranker once per model version and record its checksum:
  ```bash
  tar -czf bge-reranker-v2-m3.tar.gz -C unidocverse-service/models bge-reranker-v2-m3
  shasum -a 256 bge-reranker-v2-m3.tar.gz
  rclone copyto bge-reranker-v2-m3.tar.gz r2:unidocverse-downloads/models/bge-reranker-v2-m3.tar.gz
  ```

### 2. Set the version

Bump the version in `unidocverse-installer/src-tauri/tauri.conf.json`, commit, and tag all three
repositories (`unidocverse`, `unidocverse-service`, `unidocverse-dashboard`) with the same tag, e.g. `v0.1.7`.

### 3. Build

```bash
STARTER=1 bash build_desktop_installer_tauri.sh
```

`STARTER=1` reuses the Lite backend, leaves the reranker out, bundles SearxNG, signs every embedded
binary, and fails the build if the DMG is 2 GB or larger (GitHub's per-file limit).

### 4. Notarize and staple

```bash
DMG=unidocverse-installer/release/unidocverse_0.1.7_starter_arm64.dmg
xcrun notarytool submit "$DMG" --keychain-profile unidocverse-notarize --wait
xcrun stapler staple "$DMG"
spctl -a -t open --context context:primary-signature -v "$DMG"   # expect: Notarized Developer ID
```

### 5. Publish on GitHub Releases

```bash
shasum -a 256 "$DMG" > "$DMG.sha256"
gh release create v0.1.7 "$DMG" "$DMG.sha256" \
  --repo bommavj/unidocverse --title "UniDocVerse 0.1.7" --notes-file RELEASE_NOTES.md
```

### 6. Docker image (same version)

```bash
for arch in amd64 arm64; do
  docker buildx build --platform linux/$arch -f Dockerfile.lite -t bommavj/unidocverse:lite-$arch --push .
done
docker buildx imagetools create -t bommavj/unidocverse:lite -t bommavj/unidocverse:v0.1.7-lite \
  bommavj/unidocverse:lite-amd64 bommavj/unidocverse:lite-arm64
```

### 7. Check the release

- Download the DMG from the release page; macOS opens it without a warning.
- Fresh install: the search model downloads, then a question returns an answer with a page citation.
- `docker run` the new image; sign in and run **Integrations → Web search → Test**.

### 8. Download counts

- GitHub: `gh api repos/bommavj/unidocverse/releases --jq '.[] | {tag: .tag_name, downloads: [.assets[] | {name, download_count}]}'`
- Docker Hub: pull count on the repository page.

## Status

| Step | State |
|---|---|
| Lite backend build (`LITE=1`) | ✅ Done |
| SearxNG bundled in DMG and Docker | ✅ Done (0.1.6) |
| First-launch reranker download | ⬜ To build |
| `STARTER=1` build switch + 2 GB size guard | ⬜ To build |
| First Starter release on GitHub | ⬜ After the two items above |

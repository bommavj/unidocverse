## UniDocVerse 0.1.6

Private, on-premises document intelligence: ask questions about tax forms, notices, statements and reports, and get answers with the exact file and page they came from.

### Downloads

| Edition | File | Notes |
|---|---|---|
| **Starter** (macOS, Apple Silicon) | `unidocverse_0.1.6_starter_arm64.dmg` (attached, ~1.1 GB) | Downloads its 1.3 GB search model on first launch (checksum verified, resumes if interrupted) |
| Docker Lite (Windows / Mac / Linux) | `docker pull bommavj/unidocverse:v0.1.6-lite` | amd64 + arm64 |
| Full / Lite (macOS) | [unidocverse.com](https://unidocverse.com) | Bundled answer model (Full) or full reranker in the installer (Lite) |

Requirements: macOS 14+ on M1 or later, 16 GB memory, [Ollama](https://ollama.com) with `ollama pull mistral:7b` (or a cloud model key). Optional for forms and charts: `ollama pull gemma4`.

### New

- **Private web search** — the Research Agent can also search the web through a bundled SearxNG. Only the question's general topic is sent (names, ID numbers, amounts and document text are removed first), every search is in the audit trail, and it is off until an admin turns it on.
- **Starter edition** — a small installer published here on GitHub Releases.
- **Pilot report** — 30/60/90-day usage report for early adopters (documents processed, pages read, cited answers, time saved). Nothing is sent automatically.
- **Chart reading and model roles** — chart values read by a local vision model and checked against the page; choose a model per step (planner, answer, extraction, vision).
- **Page-accurate ingestion** — every page stored with its real page number; scans and phone photos (including HEIC) read with PaddleOCR.

### Fixed

- Data separation between organisations: document lists, research history, the morning brief and industry modules now return only the signed-in organisation's records.
- The morning brief endpoint now requires sign-in.

### Verify the download

```bash
shasum -a 256 unidocverse_0.1.6_starter_arm64.dmg   # compare with the attached .sha256
```

The DMG is signed with a Developer ID and notarized by Apple.

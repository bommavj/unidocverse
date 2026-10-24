## UniDocVerse 0.1.7

Private, on-premises document intelligence: ask questions about tax forms, notices, statements and reports, and get answers with the exact file and page they came from.

### One installer for every Mac setup

`unidocverse_0.1.7_arm64.dmg` (1.3 GB, attached) replaces the separate Full, Lite and Starter downloads. On first launch, choose how UniDocVerse answers questions:

| Choice | What downloads | Same as before |
|---|---|---|
| **Built-in model** | search model (1.3 GB) + answer model phi3:mini (2.1 GB) | Full |
| **Your own Ollama** | search model only | Lite |
| **Cloud model (your key)** | search model only | Lite with a cloud model |

Models come from the UniDocVerse download server, are checked against a pinned SHA-256 and resume if interrupted. Scans and photos are read with PaddleOCR in every setup.

Requirements: macOS 14+ on Apple Silicon (M1 or later), 16 GB memory. Optional for forms and charts: `ollama pull gemma4`.

Docker (Windows / Mac / Linux): `docker pull bommavj/unidocverse:lite`.

### Also in this release

- Private web search through a bundled SearxNG — topic-only queries, every search in the audit trail, off until an admin enables it.
- Pilot report for 30/60/90-day reviews (Governance → Pilot report).
- Data separation between organisations across documents, research history, the morning brief and industry modules; upload and job routes require sign-in.
- Report questions are no longer answered from an unrelated spreadsheet that happens to share a column name.

### Verify the download

```bash
shasum -a 256 unidocverse_0.1.7_arm64.dmg   # compare with the attached .sha256
```

Signed with a Developer ID and notarized by Apple.

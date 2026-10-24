## What's Changed

* One macOS installer for every setup — Full, Lite and Starter are now a single 1.3 GB download.
* Models download on first launch from the UniDocVerse server, checked against a pinned SHA-256 and resumed if interrupted.
* New **Built-in model** option on Home: one click downloads phi3:mini with a progress bar — no Terminal needed.
* PaddleOCR is now included in every macOS setup, so scans and phone photos are read accurately everywhere.
* Added private web search through a bundled SearxNG; only the question's general topic is sent and every search is written to the audit trail.
* Added the Pilot report (Governance → Pilot report) for 30/60/90-day early-adopter reviews.
* Fixed data separation between organisations across documents, research history, the morning brief and industry modules.
* Upload, job and brief routes now require sign-in.
* Fixed report questions being answered from an unrelated spreadsheet that shared a column name.
* Docker Lite rebuilt as `v0.1.7-lite` for amd64 and arm64.

## One installer, your choice of engine

Until now you had to pick between a 4.8 GB Full download, a 2.4 GB Lite download and a Starter build before you even knew which you needed. 0.1.7 ships **one notarized installer**. On first launch, UniDocVerse asks how it should answer questions:

| Choice | What downloads | Best for |
|---|---|---|
| **Built-in model** | search model (1.3 GB) + phi3:mini (2.1 GB) | Getting started with nothing else installed |
| **Your own Ollama** | search model only | Using `mistral:7b`, `gemma4` or any model you already run |
| **Cloud model** | search model only | Anthropic, OpenAI, Gemini and others with your own key (asks before sending, masks identifiers) |

Every choice keeps your documents on your machine. You can switch later in **Integrations**.

<p align="center">
  <img src="https://raw.githubusercontent.com/bommavj/unidocverse/main/docs/images/2026-research-agent.png" width="860" alt="A three-part question answered from the 104-page CDTFA 2023-24 Annual Report, with the source cited">
</p>

*A three-part question answered from the 104-page CDTFA 2023-24 Annual Report — $79.4 billion in sales and use tax, down 0.6%, with $34.5 billion to the General Fund — every figure cited to the report.*

## Downloads

* **macOS Lite (Apple Silicon, 1.3 GB):** `unidocverse_0.1.7_arm64.dmg` below — macOS 14+, M1 or later, 16 GB memory.
* **macOS Full (offline, 4.8 GB):** everything bundled — no downloads after install, for air-gapped or offline Macs. Download from [unidocverse.com](https://unidocverse.com/#download).
* **Docker (Windows, Mac, Linux):** `docker pull bommavj/unidocverse:v0.1.7-lite` — see the [README](https://github.com/bommavj/unidocverse#getting-started-with-docker-recommended) for the full `docker run` command.

Verify the download: `shasum -a 256 unidocverse_0.1.7_arm64.dmg` and compare with the attached `.sha256`. Signed with a Developer ID and notarized by Apple.

## Contributors

* @bommavj — design, development and release

**Full Changelog**: https://github.com/bommavj/unidocverse/compare/v0.1.6...v0.1.7 · [All versions since v0.1.0](https://github.com/bommavj/unidocverse/blob/main/CHANGELOG.md)

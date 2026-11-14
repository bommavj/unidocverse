## What's Changed

* **Immigration workspace for 33 case types**: H-1B, H-4, L-1/L-2, O-1, TN, E-3, F-1/OPT, J-1, EB-1/EB-2/EB-5, I-130, I-485, I-751, K-1, N-400 and more, each with its own questionnaire and evidence checklist.
* **People & documents**: every person on your immigration documents, with how their passport, I-94, I-797, visa, LCA, PERM, I-140, EAD and green card connect, and the problems found between them (name or date mismatches, I-94 shorter than the approval, passport expiring first, missing documents for the case).
* **Family links**: spouses from marriage certificates, children from birth certificates and the I-130 relationship box. A dependent's status (H-4, L-2, …) is checked against the principal's.
* **New clients from documents**: an uploaded passport or USCIS form proposes a client; you approve before it is created.
* Filled USCIS PDF forms are read from their form fields.
* Green cards are classified correctly, with permanent residence shown as having no end date and card expiry as an I-90 renewal reminder.
* Every correction you make to a fact, link or problem needs a reason and is kept in the change history.
* Cleaner pages: shorter titles, no filler subtitles or emoji, and a restyled Immigration area (cases list, clients board, tracker, forms, e-signature, reports).

## Downloads

* **macOS Lite (Apple Silicon, ~1.3 GB):** `unidocverse_0.1.9_arm64.dmg` below. On first launch choose a built-in model, your own Ollama, or a cloud key. macOS 14+, M1 or later, 16 GB memory.
* **macOS Full (offline, ~4.8 GB):** everything bundled, no downloads after install. **[Download Full v0.1.9](https://unidocverse-downloads.vijay-bomma.workers.dev/download/macos-full)** (also on [unidocverse.com](https://unidocverse.com/#download)).
* **Docker (Windows, Mac, Linux):** `docker pull bommavj/unidocverse:v0.1.9-lite`.

Verify the download: `shasum -a 256 unidocverse_0.1.9_arm64.dmg` and compare with the attached `.sha256`. Signed with a Developer ID and notarized by Apple.

## Contributors

* @bommavj — design, development and release

**Full Changelog**: https://github.com/bommavj/unidocverse/compare/v0.1.8...v0.1.9 · [All versions since v0.1.0](https://github.com/bommavj/unidocverse/blob/main/CHANGELOG.md)

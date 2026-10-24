## What's Changed

* New **Statistics** page: documents processed, pages read, questions answered, answer quality and documents by type — for 7 days to 12 months, counts only.
* New **Share your experience** (Help): rating, comment and optional usage counts, with a preview of exactly what is sent. Nothing is sent until you press Send.
* Spreadsheets answer **change between periods** questions: "which sector had the largest % drop between March and April 2020" → General merchandise stores, −63.95%, computed over every row.
* Spreadsheets with a title row above the real column headers are now read correctly.
* "Excluding totals" now leaves the Total / ALL rows out instead of selecting them.
* Spreadsheet answers grouped by a column carry a chart, so **Visualize** opens them in Analytics.
* Fixed: after choosing **Send to** a cloud model, the same consent question could appear again. Your choice now applies to every step of the answer, and notes such as "Answered by Google Gemini" are shown.
* The Research header shows the cloud model when one is active.
* **Refresh models** in Integrations (and automatically when you return to the app) — models pulled with Ollama appear without reopening the page.

## Answers you can share

0.1.8 makes it easy to see — and show others — what UniDocVerse is doing for your organisation. **Statistics** summarises usage and answer quality for any period, and one click shares it: with your team as a summary, PDF or data file, or with us through **Share your experience**. Every share is opt-in and previewed first; the app still sends nothing on its own. See the [privacy note](https://unidocverse.com/company/privacy).

<p align="center">
  <img src="https://raw.githubusercontent.com/bommavj/unidocverse/main/docs/images/analytics.gif" width="860" alt="Spreadsheet analytics: total sales by region computed over 1,500 rows, then visualized as charts">
</p>

## Downloads

* **macOS Lite (Apple Silicon, ~1.3 GB):** `unidocverse_0.1.8_arm64.dmg` below — on first launch choose a built-in model, your own Ollama, or a cloud key. macOS 14+, M1 or later, 16 GB memory.
* **macOS Full (offline, ~4.8 GB):** everything bundled, no downloads after install — from [unidocverse.com](https://unidocverse.com/#download).
* **Docker (Windows, Mac, Linux):** `docker pull bommavj/unidocverse:v0.1.8-lite`.

Verify the download: `shasum -a 256 unidocverse_0.1.8_arm64.dmg` and compare with the attached `.sha256`. Signed with a Developer ID and notarized by Apple.

## Contributors

* @bommavj — design, development and release

**Full Changelog**: https://github.com/bommavj/unidocverse/compare/v0.1.7...v0.1.8 · [All versions since v0.1.0](https://github.com/bommavj/unidocverse/blob/main/CHANGELOG.md)

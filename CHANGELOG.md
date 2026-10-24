# Changelog

All notable changes to UniDocVerse, designed and built by [@bommavj](https://github.com/bommavj) since v0.1.0. Downloads for each release are on the [Releases](https://github.com/bommavj/unidocverse/releases) page.

---

## v0.1.8 — 2026-10-24 · Latest

### What's Changed

* Statistics page: usage, answer quality and documents by type, with share options (summary, PDF, data, or Share with UniDocVerse).
* Share your experience: opt-in feedback with a preview of exactly what is sent.
* Spreadsheets: change-between-periods questions, title rows above headers, "excluding totals", and charts for grouped answers.
* Fixed the cloud consent question appearing again after "Send to"; cloud-model notes now shown.
* Research header shows the active cloud model; Refresh models in Integrations.

[Release notes](https://github.com/bommavj/unidocverse/releases/tag/v0.1.8)

**Contributor:** [@bommavj](https://github.com/bommavj)

---

## v0.1.7 — 2026-10-23

### What's Changed

* One macOS installer for every setup — Full, Lite and Starter are now a single 1.3 GB download.
* Models download on first launch from the UniDocVerse server, checked against a pinned SHA-256 and resumed if interrupted.
* New **Built-in model** option on Home: one click downloads phi3:mini with a progress bar.
* PaddleOCR included in every macOS setup.
* Pilot report (Governance → Pilot report) for 30/60/90-day early-adopter reviews.
* Data separation between organisations across documents, research history, the morning brief and industry modules; upload, job and brief routes require sign-in.
* Report questions are no longer answered from an unrelated spreadsheet that shares a column name.
* Docker Lite `v0.1.7-lite` for amd64 and arm64.

[Release notes](https://github.com/bommavj/unidocverse/releases/tag/v0.1.7)

**Contributor:** [@bommavj](https://github.com/bommavj)

---

## v0.1.6 — 2026-10-23

### What's Changed

* Private web search for the Research Agent through a bundled SearxNG — topic-only queries, every search in the audit trail, off until an admin enables it.
* Starter edition: a small installer that downloads its search model on first launch.
* Chart reading with a local vision model; values checked against the page.
* Model roles: a different model for planning, answering, extraction and vision.
* Answers say when a chart's values couldn't be read instead of guessing.
* Docker Lite with SearxNG for amd64 and arm64.

[Release notes](https://github.com/bommavj/unidocverse/releases/tag/v0.1.6)

**Contributor:** [@bommavj](https://github.com/bommavj)

---

## v0.1.5 — 2026-10-21

### Accuracy rebuild

Every page is now stored with its real page number, read the best way for that page: the PDF text layer where it exists, PaddleOCR for scans and phone photos, with noise from barcodes and photos filtered out.

* Search rebuilt: keyword + vector candidates fused and reranked with `bge-reranker-v2-m3`, with neighbouring passages included.
* Multi-part questions are split and searched part by part.
* Look-alike documents ("my 2024 W-2", "the Jan 9 pay stub") told apart by dates and years.
* Forms (W-2, 1099, 1040, passports, USCIS notices) read box by box with a local vision model; every value checked against the page.
* Questions naming "Table 2", "Schedule C" or "page 47" go straight to that page.

### Also

* Cloud models with your own key (Anthropic, OpenAI, Gemini, xAI, Mistral and others): asks before sending, masks identifiers, never-send document types, monthly budget.
* Integrations page with tiles, send history and Salesforce.
* Morning brief of what needs attention today; approvals confirmed inside the Research chat.
* Append-only audit trail with retention and legal hold.
* In-app Help page.
* First Docker Lite image (no model inside; uses Ollama on the host or a cloud key).

**Contributor:** [@bommavj](https://github.com/bommavj)

---

## v0.1.4 — 2026-10-16

### What's Changed

* Research answers can read whole documents when they fit, not just matching passages.
* Answers check that every figure appears in the cited source and say so when it doesn't.
* Named documents and form codes ("the Acme W-2", "1099-NEC") find the right file.
* Document types grouped into families so related forms are searched together.
* Fixed the research stream running questions as the default organisation.

**Contributor:** [@bommavj](https://github.com/bommavj)

---

## v0.1.3 — 2026-10-11

### What's Changed

* Immigration suite: case pages, case tasks, and tracking of visa and status documents by expiry.
* API tokens for integrations, with read-only scopes.
* Contract comparison.
* Industry modules switched on or off per organisation.
* Dashboard redesign: top bar, menus that follow the switched-on modules.
* Desktop app moved to port 7979; fresh installs run every database migration cleanly.

**Contributor:** [@bommavj](https://github.com/bommavj)

---

## v0.1.2 — 2026-08-18

### What's Changed

* Ten domain AI agents (insurance, immigration, legal, finance, HR, healthcare, real estate, supply chain, operations, compliance).
* AI Reports: domain-scoped views, PDF download and pagination.
* Documents can be filtered by client.

**Contributor:** [@bommavj](https://github.com/bommavj)

---

## v0.1.1 — 2026-08-13

### What's Changed

* First public release of the service and dashboard repositories under the Apache 2.0 licence.
* Docker image with the answer model, Postgres and migrations included.
* Every API request from the dashboard carries authentication; ask and research endpoints require sign-in.
* Embeddable chatbot with session tokens.

**Contributor:** [@bommavj](https://github.com/bommavj)

---

## v0.1.0 — 2026-02-12

### What's Changed

* First macOS app for Apple Silicon: upload documents and ask questions, running entirely on the Mac.
* Architecture, data-flow and deployment documentation.

**Contributor:** [@bommavj](https://github.com/bommavj)

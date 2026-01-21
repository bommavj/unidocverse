<p align="center">
  <img src="https://raw.githubusercontent.com/<your-username>/unidocverse/main/logo.png" width="160" alt="UniDocVerse Logo">
</p>

<h1 align="center">UniDocVerse</h1>

<p align="center">
  <strong>Universal AI Document Intelligence for Law, Finance, Healthcare, Insurance, Government, Education, Real Estate, HR, Compliance, Manufacturing, and Enterprises Worldwide.</strong><br/>
  One platform for every document, every workflow, every industry — built with privacy, legality, and global trust at its core.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Docker-Ready-blue?logo=docker&logoColor=white" />
  <img src="https://img.shields.io/badge/Python-3.11+-yellow?logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Angular-17-red?logo=angular&logoColor=white" />
  <img src="https://img.shields.io/github/license/<your-username>/unidocverse?color=brightgreen" />
  <img src="https://img.shields.io/github/stars/<your-username>/unidocverse?style=social" />
</p>

---

## 🔐 Privacy‑First Architecture (Phase 1 → Phase 2)

### Phase 1 — 100% Local, Private, Offline‑Ready  
UniDocVerse is engineered for industries where confidentiality, compliance, and legal integrity are mandatory.  
Everything runs **locally**, ensuring:

- No cloud calls  
- No external APIs  
- No data leaves your environment  
- No telemetry, tracking, or analytics  
- No licensing violations  
- No compliance conflicts  
- No internet required  
- Fully self‑contained deployment  

All AI processing — OCR, extraction, embeddings, analytics, classification, search — happens **inside your infrastructure**.

Perfect for:

- Law firms  
- Banks  
- Hospitals  
- Insurance  
- Government  
- Compliance teams  
- Regulated enterprises  

**Your documents never leave your machine.  
Your data stays yours. Always.**

---

### Phase 2 — Secure Cloud Deployment (Optional)  
Phase 2 introduces optional cloud scalability while preserving enterprise‑grade privacy.

Planned capabilities:

- Fully managed cloud deployment  
- Multi‑tenant SaaS architecture  
- Auto‑scaling pipelines  
- Cloud vector search  
- Global team access  
- Encrypted storage & transport  
- SOC2 / HIPAA‑ready design  
- Hybrid mode (local + cloud)

**Cloud is optional — never required.  
Privacy remains the foundation.**

---

## 🧠 Local AI Models Included — Legally Safe, Redistribution‑Friendly

UniDocVerse ships with **all‑mpnet‑base‑v2**, a high‑quality sentence‑embedding model that is:

- ✅ Redistribution‑permitted  
- ✅ Commercial‑use allowed  
- ✅ Fully local  
- ✅ No external downloads required  
- ✅ No internet needed  
- ✅ No licensing conflicts  
- ✅ No legal exposure  

This ensures UniDocVerse remains:

- Safe to distribute  
- Safe to deploy  
- Safe for enterprise environments  
- Safe for regulated industries  
- Safe for global usage  

### Why all‑mpnet‑base‑v2?

- Excellent semantic embedding performance  
- Lightweight and fast  
- Works offline  
- Ideal for vector search, clustering, classification, and analytics  
- Stable and widely trusted  

### Thank You to the Model Authors  
We extend our appreciation to the researchers and engineers who created **all‑mpnet‑base‑v2** and made it available under a license that supports:

- Local deployment  
- Redistribution  
- Commercial usage  
- Privacy‑first applications  

Their work enables UniDocVerse to deliver **high‑quality AI capabilities without compromising privacy, legality, or user trust**.

---

## 🔒 Why UniDocVerse Is Different

### 1. Unlimited Files — No Quotas, No Limits  
Process thousands or millions of documents.  
No file count limits. No size caps. No usage quotas.  
Your hardware is the only boundary.

### 2. 100% Local Processing — Zero Cloud Dependency  
No OpenAI. No Google. No AWS. No Azure.  
No external APIs. No cloud sync. No telemetry.  
Everything runs inside your infrastructure.

### 3. Legally Clean, Compliance‑Safe, Enterprise‑Ready  
No licensing violations.  
No copyright conflicts.  
No privacy breaches.  
No regulatory offenses.  
No cross‑border data transfer risks.

### 4. Cloud Optional — Not Required  
You choose:

- Local  
- On‑prem  
- Hybrid  
- Cloud (Phase 2)

UniDocVerse never forces cloud usage.

---

## 🚀 Overview

UniDocVerse is a universal, cross‑industry AI platform for document understanding, analytics, semantic search, and workflow automation.  
It transforms unstructured documents into structured insights using multi‑agent AI, vector search, and enterprise‑grade processing pipelines.

---

## ✨ Features

| Category | Capabilities |
|---------|--------------|
| **AI Document Understanding** | OCR, text extraction, table parsing, metadata, entity detection |
| **Semantic Intelligence** | Summaries, key points, insights, classifications, embeddings |
| **Analytics Engine** | Auto‑generated dashboards, metrics, charts, visualizations |
| **Search & Retrieval** | Vector search (pgvector), semantic ranking, keyword search |
| **Workflow Automation** | Multi‑agent LangGraph pipelines, conditional routing |
| **Universal Format Support** | PDF, DOCX, XLSX, PPTX, CSV, JSON, HTML, XML, TXT, JPG, PNG, HEIC, EML, MSG, ZIP, and more |
| **Enterprise‑Grade Architecture** | FastAPI backend, Angular frontend, PostgreSQL + pgvector |
| **Deployment Ready** | Docker Compose, on‑prem, cloud, hybrid |

---

## 📁 Supported File Types

### 📄 Documents  
PDF (.pdf)  
DOC, DOCX (.doc, .docx)  
ODT (.odt)  
RTF (.rtf)  
TXT (.txt)  
HTML (.html, .htm)

### 📊 Spreadsheets  
XLS, XLSX (.xls, .xlsx)  
CSV (.csv)  
TSV (.tsv)  
ODS (.ods)  
Parquet (.parquet)  
JSON (.json)

### 📑 Presentations  
PPT, PPTX (.ppt, .pptx)  
ODP (.odp)

### 🖼️ Images (with OCR)  
JPG, JPEG (.jpg, .jpeg)  
PNG (.png)  
WebP (.webp)  
HEIC, HEIF (.heic, .heif)  
TIFF (.tif, .tiff)  
BMP (.bmp)

### 📬 Emails  
EML (.eml)  
MSG (.msg)  
MBOX (.mbox)

### 📦 Archives  
ZIP (.zip)  
TAR, GZ (.tar, .gz, .tgz)

### 🧠 Machine Formats  
JSONL (.jsonl)  
XML (.xml)  
YAML (.yaml, .yml)

---

## 🏗️ System Architecture

```mermaid
flowchart LR

    subgraph Client
        UI[Angular Dashboard]
    end

    subgraph Backend
        API[FastAPI Service]
        Workflow[LangGraph Multi‑Agent Engine]
        Analytics[Analytics Auto‑Generator]
    end

    subgraph Database
        PG[(PostgreSQL + pgvector)]
    end

    UI -->|REST / API Calls| API
    API --> Workflow
    Workflow --> Analytics
    Workflow --> PG
    API --> PG

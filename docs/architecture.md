# UniDocVerse Architecture

UniDocVerse is built as a modular, privacy‑first, fully local document‑intelligence platform.  
The architecture is engineered for:

- Deterministic multi‑agent workflows  
- High‑volume document processing  
- Full offline capability  
- Enterprise‑grade reliability  
- Extensibility across industries  
- Zero cloud dependency  

This document provides a complete overview of the system architecture, including backend, frontend, database, agentic workflow, analyzers, and data flow.

---

# 1. High‑Level Architecture Overview

UniDocVerse consists of three major layers:

- **Client** — Angular dashboard  
- **Backend** — FastAPI + LangGraph multi‑agent engine  
- **Database** — PostgreSQL + pgvector  

## High‑Level System Architecture

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
```

## Agentic Workflow Pipeline

```mermaid
flowchart TD

    INGEST[Ingest Node] --> PARSE[Parse Node]
    PARSE --> CLEANUP[Cleanup Node]
    CLEANUP --> SPECIFIC[Specific Analysis Node]
    SPECIFIC --> ANALYZE[Analyze Node]
    ANALYZE --> SEARCHPREP[Search Prep Node]
    SEARCHPREP --> QC[Quality Check Node]
    QC --> INSIGHT[Insight Node]
    INSIGHT --> METRICS[Calculate Metrics Node]
    METRICS --> ENTITY[Entity Linking Node]
    ENTITY --> FINALIZE[Finalize Node]
```

```mermaid
flowchart TB

    %% ============================
    %% COLOR STYLES
    %% ============================
    classDef client fill:#E3F2FD,stroke:#1E88E5,stroke-width:1.5px,color:#0D47A1;
    classDef backend fill:#E8F5E9,stroke:#43A047,stroke-width:1.5px,color:#1B5E20;
    classDef workflow fill:#F3E5F5,stroke:#8E24AA,stroke-width:1.5px,color:#4A148C;
    classDef ai fill:#E0F7FA,stroke:#00838F,stroke-width:1.5px,color:#004D40;
    classDef data fill:#FFF3E0,stroke:#FB8C00,stroke-width:1.5px,color:#E65100;
    classDef analytics fill:#FFFDE7,stroke:#FDD835,stroke-width:1.5px,color:#F9A825;

    %% ============================
    %% CLIENT LAYER
    %% ============================
    subgraph CLIENT["Client Layer"]
        UI[Angular Dashboard<br/>• Upload<br/>• Preview<br/>• Insights<br/>• Search]:::client
    end

    %% ============================
    %% BACKEND LAYER
    %% ============================
    subgraph BACKEND["Backend Layer (FastAPI)"]
        API[REST API Gateway<br/>• Routing<br/>• Validation]:::backend
        WORKFLOW[LangGraph Multi‑Agent Engine<br/>• Orchestration<br/>• Node Execution]:::workflow
        ANALYTICS[Analytics Engine<br/>• Metrics<br/>• Charts<br/>• Aggregations]:::analytics
    end

    %% ============================
    %% AGENTIC WORKFLOW PIPELINE
    %% ============================
    subgraph PIPELINE["Agentic Workflow Pipeline"]
        INGEST[Ingest<br/>Normalize Input]:::workflow --> 
        PARSE[Parse<br/>Extract Text/Tables]:::workflow --> 
        CLEANUP[Cleanup<br/>Noise Removal]:::workflow --> 
        SPECIFIC[Specific Analysis<br/>Document‑Type Logic]:::workflow --> 
        ANALYZE[Analyze<br/>Summaries & Insights]:::workflow --> 
        SEARCHPREP[Search Prep<br/>Embeddings & Chunking]:::workflow --> 
        QC[Quality Check<br/>Validation]:::workflow --> 
        INSIGHT[Insight Engine<br/>Flags & Recommendations]:::workflow --> 
        METRICS[Metrics Engine<br/>Aggregations]:::workflow --> 
        ENTITY[Entity Linking<br/>Relationships]:::workflow --> 
        FINALIZE[Finalize<br/>Output Assembly]:::workflow
    end

    %% ============================
    %% AI MODELS LAYER
    %% ============================
    subgraph AI["Local AI Models"]
        MODEL[all‑mpnet‑base‑v2<br/>• Embeddings<br/>• Semantic Search]:::ai
    end

    %% ============================
    %% DATA LAYER
    %% ============================
    subgraph DATA["Data Layer (Local Only)"]
        PG[(PostgreSQL)]:::data
        VEC[(pgvector Index)]:::data
        STORAGE[(Local File Storage)]:::data
    end

    %% ============================
    %% FLOWS
    %% ============================
    UI -->|REST Calls| API
    API --> WORKFLOW

    WORKFLOW --> INGEST
    FINALIZE --> ANALYTICS

    WORKFLOW --> MODEL
    WORKFLOW --> PG
    WORKFLOW --> VEC

    API --> PG
    API --> STORAGE

    ANALYTICS --> UI
    PG --> UI
    VEC --> UI
```
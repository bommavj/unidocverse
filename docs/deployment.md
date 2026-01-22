# Deployment Guide  
### Local, On‑Prem, and Air‑Gapped Installation

UniDocVerse is designed for flexible deployment across:

- Developer laptops  
- On‑prem servers  
- Air‑gapped environments  
- Private clouds  
- Docker‑based clusters  

---

# 1. Deployment Architecture

```mermaid
flowchart TB

    classDef env fill:#ECEFF1,stroke:#546E7A,stroke-width:1.5px,color:#263238;
    classDef comp fill:#E8F5E9,stroke:#43A047,stroke-width:1.5px,color:#1B5E20;
    classDef data fill:#FFF3E0,stroke:#FB8C00,stroke-width:1.5px,color:#E65100;

    subgraph USER_ENV["Local / On‑Prem Environment"]
        subgraph HOST["Host Machine / Server"]
            DOCKER[Docker Runtime]:::env

            subgraph APP["UniDocVerse Stack"]
                UI[Angular Frontend]:::comp
                API[FastAPI Backend]:::comp
                DB[PostgreSQL + pgvector]:::data
                STORAGE[(Local Volume)]:::data
            end
        end
    end

    UI --> API
    API --> DB
    API --> STORAGE

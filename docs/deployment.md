# Deployment Guide 

### Local, On‑Prem

UniDocVerse is designed for flexible deployment across:

- Developer laptops  
- On‑prem servers
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
```


# Cross‑Platform Packaging Plan  
A clean, professional roadmap for delivering UniDocVerse as a native, offline‑ready application across macOS, Windows, and Linux.

---

# 🍎 1. macOS Build (.app + .dmg)

You will get:

- A native **UniDocVerse.app**
- A **double‑clickable launcher**
- A **.dmg installer** with drag‑to‑Applications support

### Inside the `.app` bundle:

### The launcher will:

- Start embedded PostgreSQL  
- Run migrations  
- Start backend  
- Start frontend  
- Open browser  

### Tools used:

- `appify` or a custom shell launcher  
- `create-dmg` for packaging  
- Optional: **Platypus** for a polished GUI wrapper  

---

# 🪟 2. Windows Build (.exe Installer)

You will get:

- A native **UniDocVerse.exe**
- A Windows installer (**NSIS** or **Inno Setup**)
- A Start Menu shortcut
- Optional: background service wrapper

### Inside the install directory:


### The launcher will:

- Start embedded PostgreSQL (Windows binaries)  
- Run migrations  
- Start backend (python.exe inside venv)  
- Start frontend (serve dist)  
- Open browser  

### Tools used:

- **Inno Setup** (recommended)  
- Or **NSIS**  
- Optional: **PyInstaller** to wrap backend launcher into an `.exe`  

---

# 🐧 3. Linux Build (AppImage)

You will get:

- A single portable **UniDocVerse.AppImage**
- No installation required
- Works on Ubuntu, Fedora, Arch, etc.

### Inside the AppImage:


### Tools used:

- `appimagetool`
- `linuxdeploy`

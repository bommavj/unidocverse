use std::fs;
use std::path::{Path, PathBuf};
use std::process::{Command, Child};
use std::thread;
use std::time::{Duration, Instant};
use std::io::Write;
use std::net::TcpStream;
use tauri::Manager;

#[cfg(target_os = "windows")]
const POSTGRES_BIN: &str = "postgres.exe";
#[cfg(not(target_os = "windows"))]
const POSTGRES_BIN: &str = "postgres";

#[cfg(target_os = "windows")]
const INITDB_BIN: &str = "initdb.exe";
#[cfg(not(target_os = "windows"))]
const INITDB_BIN: &str = "initdb";

#[cfg(target_os = "windows")]
const PSQL_BIN: &str = "psql.exe";
#[cfg(not(target_os = "windows"))]
const PSQL_BIN: &str = "psql";

#[cfg(target_os = "windows")]
const CREATEDB_BIN: &str = "createdb.exe";
#[cfg(not(target_os = "windows"))]
const CREATEDB_BIN: &str = "createdb";

#[cfg(target_os = "windows")]
const BACKEND_BIN: &str = "unidocverse-backend.exe";
#[cfg(not(target_os = "windows"))]
const BACKEND_BIN: &str = "unidocverse-backend";

// State structure to track background child processes
struct AppState {
    pg_child: std::sync::Mutex<Option<Child>>,
    backend_child: std::sync::Mutex<Option<Child>>,
    searx_child: std::sync::Mutex<Option<Child>>,
}

/// Bundled SearxNG (web search for the Research Agent) on 127.0.0.1:8888. Skipped when the
/// port is already taken (the organisation runs its own) or the bundle has no SearxNG.
/// Web search itself stays off until an admin turns it on in Integrations.
fn start_searxng(resource_dir: &Path, logs_dir: &Path) -> Option<Child> {
    let root = resource_dir.join("searxng");
    let python = root.join("python").join("bin").join("python3");
    if !python.exists() || TcpStream::connect("127.0.0.1:8888").is_ok() {
        return None;
    }
    let seed = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_nanos()).unwrap_or(0) ^ ((std::process::id() as u128) << 64);
    let log = fs::File::create(logs_dir.join("searxng.log")).ok()?;
    let err = log.try_clone().ok()?;
    let child = Command::new(&python)
        .args(["-m", "searx.webapp"])
        .env("SEARXNG_SETTINGS_PATH", root.join("settings.yml"))
        .env("SEARXNG_SECRET", format!("{:032x}", seed))
        .env("PYTHONDONTWRITEBYTECODE", "1")
        .stdout(std::process::Stdio::from(log))
        .stderr(std::process::Stdio::from(err))
        .spawn();
    match child {
        Ok(c) => { println!("🌐 SearxNG started on 127.0.0.1:8888"); Some(c) }
        Err(e) => { eprintln!("SearxNG not started: {}", e); None }
    }
}

// ── Claude Desktop MCP auto-config ───────────────────────────────────────────

const MCP_SSE_URL: &str = "http://localhost:7979/mcp/sse";

/// Read a JSON file; return empty object if missing or unparseable.
fn read_json(path: &PathBuf) -> serde_json::Value {
    fs::read_to_string(path)
        .ok()
        .and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or(serde_json::json!({}))
}

/// Write a JSON value as pretty-printed JSON, creating parent dirs as needed.
fn write_json(path: &PathBuf, value: &serde_json::Value) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| format!("mkdir {}: {}", parent.display(), e))?;
    }
    let pretty = serde_json::to_string_pretty(value)
        .map_err(|e| format!("serialize: {}", e))?;
    fs::write(path, pretty).map_err(|e| format!("write {}: {}", path.display(), e))
}

/// Returns (config_path, app_detection_path).
/// app_detection_path is checked to see if the client is installed at all.
fn client_paths(client: &str, home: &str) -> Option<(PathBuf, PathBuf)> {
    let h = PathBuf::from(home);
    match client {
        "claude-desktop" => {
            let app_dir = h.join("Library").join("Application Support").join("Claude");
            let cfg     = app_dir.join("claude_desktop_config.json");
            Some((cfg, app_dir))
        }
        "cursor" => {
            let app_dir = h.join(".cursor");
            let cfg     = app_dir.join("mcp.json");
            Some((cfg, app_dir))
        }
        "zed" => {
            let app_dir = h.join(".config").join("zed");
            let cfg     = app_dir.join("settings.json");
            // Zed is "installed" if its settings dir exists OR the app bundle does
            let detection = PathBuf::from("/Applications/Zed.app");
            let detect = if detection.exists() { detection } else { app_dir.clone() };
            Some((cfg, detect))
        }
        "continue" => {
            let app_dir = h.join(".continue");
            let cfg     = app_dir.join("config.json");
            Some((cfg, app_dir))
        }
        "windsurf" => {
            let app_dir = h.join(".codeium").join("windsurf");
            let cfg     = app_dir.join("mcp_config.json");
            Some((cfg, app_dir))
        }
        _ => None,
    }
}

/// Merge the UniDocVerse MCP entry into the client's config JSON.
/// Returns the mutated value.
fn merge_mcp_entry(client: &str, mut config: serde_json::Value) -> serde_json::Value {
    match client {
        // mcpServers.unidocverse = { url, type }
        "claude-desktop" => {
            if config.get("mcpServers").is_none() {
                config["mcpServers"] = serde_json::json!({});
            }
            config["mcpServers"]["unidocverse"] = serde_json::json!({
                "url": MCP_SSE_URL, "type": "sse"
            });
        }
        // mcpServers.unidocverse = { url, transport }
        "cursor" => {
            if config.get("mcpServers").is_none() {
                config["mcpServers"] = serde_json::json!({});
            }
            config["mcpServers"]["unidocverse"] = serde_json::json!({
                "url": MCP_SSE_URL, "transport": "sse"
            });
        }
        // context_servers.unidocverse = { command: { url } }
        "zed" => {
            if config.get("context_servers").is_none() {
                config["context_servers"] = serde_json::json!({});
            }
            config["context_servers"]["unidocverse"] = serde_json::json!({
                "command": { "url": MCP_SSE_URL }
            });
        }
        // experimental.modelContextProtocolServers — deduplicated array entry
        "continue" => {
            let entry = serde_json::json!({
                "transport": { "type": "sse", "url": MCP_SSE_URL }
            });
            if config.get("experimental").is_none() {
                config["experimental"] = serde_json::json!({});
            }
            let servers = config["experimental"]["modelContextProtocolServers"]
                .as_array_mut();
            if let Some(arr) = servers {
                let already = arr.iter().any(|e| {
                    e.get("transport")
                     .and_then(|t| t.get("url"))
                     .and_then(|u| u.as_str()) == Some(MCP_SSE_URL)
                });
                if !already { arr.push(entry); }
            } else {
                config["experimental"]["modelContextProtocolServers"] =
                    serde_json::json!([entry]);
            }
        }
        // mcpServers.unidocverse = { serverUrl, transport }
        "windsurf" => {
            if config.get("mcpServers").is_none() {
                config["mcpServers"] = serde_json::json!({});
            }
            config["mcpServers"]["unidocverse"] = serde_json::json!({
                "serverUrl": MCP_SSE_URL, "transport": "sse"
            });
        }
        _ => {}
    }
    config
}

/// Auto-configure any supported MCP client.
/// Returns "configured", "already_configured", or "not_installed".
fn configure_mcp_client(client: &str) -> Result<String, String> {
    let home = std::env::var("HOME").map_err(|_| "HOME not set".to_string())?;
    let (cfg_path, detect_path) = client_paths(client, &home)
        .ok_or_else(|| format!("Unknown client: {}", client))?;

    if !detect_path.exists() {
        return Ok("not_installed".to_string());
    }

    let existing = read_json(&cfg_path);

    // Check if already up to date (avoids unnecessary writes)
    let already = match client {
        "continue" => {
            existing.get("experimental")
                .and_then(|e| e.get("modelContextProtocolServers"))
                .and_then(|a| a.as_array())
                .map(|arr| arr.iter().any(|e| {
                    e.get("transport")
                     .and_then(|t| t.get("url"))
                     .and_then(|u| u.as_str()) == Some(MCP_SSE_URL)
                }))
                .unwrap_or(false)
        }
        "zed" => {
            existing.get("context_servers")
                .and_then(|c| c.get("unidocverse"))
                .and_then(|u| u.get("command"))
                .and_then(|c| c.get("url"))
                .and_then(|u| u.as_str()) == Some(MCP_SSE_URL)
        }
        "windsurf" => {
            existing.get("mcpServers")
                .and_then(|m| m.get("unidocverse"))
                .and_then(|u| u.get("serverUrl"))
                .and_then(|u| u.as_str()) == Some(MCP_SSE_URL)
        }
        _ => {
            existing.get("mcpServers")
                .and_then(|m| m.get("unidocverse"))
                .and_then(|u| u.get("url"))
                .and_then(|u| u.as_str()) == Some(MCP_SSE_URL)
        }
    };

    if already {
        println!("{} already configured for UniDocVerse MCP.", client);
        return Ok("already_configured".to_string());
    }

    let updated = merge_mcp_entry(client, existing);
    write_json(&cfg_path, &updated)?;

    println!("✅ {} configured — wrote {}", client, cfg_path.display());
    Ok("configured".to_string())
}

/// Tauri command — auto-configure any MCP client by name.
/// Returns "configured" | "already_configured" | "not_installed"
#[tauri::command]
fn connect_mcp_client(client: String) -> Result<String, String> {
    configure_mcp_client(&client)
}

// Helper: Copy directory recursively
fn copy_dir_all(src: impl AsRef<Path>, dst: impl AsRef<Path>) -> std::io::Result<()> {
    fs::create_dir_all(&dst)?;
    for entry in fs::read_dir(src)? {
        let entry = entry?;
        let ty = entry.file_type()?;
        if ty.is_dir() {
            copy_dir_all(entry.path(), dst.as_ref().join(entry.file_name()))?;
        } else {
            fs::copy(entry.path(), dst.as_ref().join(entry.file_name()))?;
        }
    }
    Ok(())
}

// Helper: Make binaries inside postgres bin directory executable on macOS/Linux
#[cfg(unix)]
fn make_executable(dir: &Path) -> std::io::Result<()> {
    use std::os::unix::fs::PermissionsExt;
    let bin_dir = dir.join("bin");
    if bin_dir.exists() {
        for entry in fs::read_dir(bin_dir)? {
            let entry = entry?;
            let path = entry.path();
            if path.is_file() {
                let mut perms = fs::metadata(&path)?.permissions();
                perms.set_mode(0o755);
                fs::set_permissions(&path, perms)?;
            }
        }
    }
    Ok(())
}

#[cfg(not(unix))]
fn make_executable(_dir: &Path) -> std::io::Result<()> {
    Ok(())
}

// Helper: Run SQL query via psql binary
fn run_psql(postgres_bin_dir: &Path, sql: &str, db: &str, user: &str) -> Result<String, String> {
    let psql_path = postgres_bin_dir.join(PSQL_BIN);
    let output = Command::new(psql_path)
        .args(&[
            "-h", "localhost",
            "-p", "54321",
            "-U", user,
            "-d", db,
            "-c", sql
        ])
        .output()
        .map_err(|e| format!("Failed to run psql: {}", e))?;
    
    if output.status.success() {
        Ok(String::from_utf8_lossy(&output.stdout).to_string())
    } else {
        Err(String::from_utf8_lossy(&output.stderr).to_string())
    }
}

// Helper: Run SQL file via psql binary
fn run_migration_file(postgres_bin_dir: &Path, file_path: &Path, db: &str, user: &str) -> Result<(), String> {
    let psql_path = postgres_bin_dir.join(PSQL_BIN);
    let output = Command::new(psql_path)
        .args(&[
            "-h", "localhost",
            "-p", "54321",
            "-U", user,
            "-d", db,
            "-f", file_path.to_str().unwrap()
        ])
        .output()
        .map_err(|e| format!("Failed to run psql migration: {}", e))?;
    
    if output.status.success() {
        Ok(())
    } else {
        Err(String::from_utf8_lossy(&output.stderr).to_string())
    }
}

// Helper: Run Flyway-compatible migrations
fn run_migrations(pg_bin_dir: &Path, migrations_dir: &Path) -> Result<(), String> {
    // Create flyway_schema_history table if missing
    let create_table_sql = "
      CREATE TABLE IF NOT EXISTS public.flyway_schema_history (
        installed_rank SERIAL PRIMARY KEY,
        version VARCHAR(50),
        description VARCHAR(200) NOT NULL,
        type VARCHAR(20) NOT NULL,
        script VARCHAR(1000) NOT NULL,
        checksum INTEGER,
        installed_by VARCHAR(100) NOT NULL,
        installed_on TIMESTAMP NOT NULL DEFAULT NOW(),
        execution_time INTEGER NOT NULL,
        success BOOLEAN NOT NULL
      );
      CREATE UNIQUE INDEX IF NOT EXISTS flyway_schema_history_version_idx 
        ON public.flyway_schema_history (version);
    ";
    let _ = run_psql(pg_bin_dir, create_table_sql, "unidocverse_db", "unidocverse")?;
    
    // Read and sort SQL scripts
    let mut entries = fs::read_dir(migrations_dir)
        .map_err(|e| format!("Failed to read migrations directory: {}", e))?
        .filter_map(|e| e.ok())
        .map(|e| e.path())
        .filter(|path| {
            if let Some(filename) = path.file_name().and_then(|f| f.to_str()) {
                filename.starts_with('V') && filename.ends_with(".sql")
            } else {
                false
            }
        })
        .collect::<Vec<PathBuf>>();
        
    entries.sort_by(|a, b| {
        let get_version = |path: &Path| -> Vec<u32> {
            let name = path.file_name().unwrap().to_str().unwrap();
            let end_idx = name.find("__").unwrap_or(name.len());
            name[1..end_idx]
                .split('.')
                .map(|s| s.parse::<u32>().unwrap_or(0))
                .collect()
        };
        get_version(a).cmp(&get_version(b))
    });
    
    println!("Found {} migration scripts to evaluate", entries.len());
    
    for entry in entries {
        let filename = entry.file_name().unwrap().to_str().unwrap();
        let end_idx = filename.find("__").unwrap_or(filename.len());
        let version = &filename[1..end_idx];
        let description = if end_idx < filename.len() {
            filename[end_idx+2..filename.len()-4].replace('_', " ")
        } else {
            filename.to_string()
        };
        
        let check_sql = format!(
            "SELECT 1 FROM public.flyway_schema_history WHERE version = '{}' AND success = true;",
            version
        );
        let check_res = run_psql(pg_bin_dir, &check_sql, "unidocverse_db", "unidocverse")?;
        
        if check_res.contains("(1 row)") || check_res.contains("1 row") {
            println!("  ✓ Migration {} already applied", version);
            continue;
        }
        
        println!("  ▶ Applying migration {}: {}", version, description);
        let start_time = Instant::now();
        
        match run_migration_file(pg_bin_dir, &entry, "unidocverse_db", "unidocverse") {
            Ok(()) => {
                let elapsed = start_time.elapsed().as_millis() as u32;
                let insert_sql = format!(
                    "INSERT INTO public.flyway_schema_history (version, description, type, script, installed_by, execution_time, success) \
                     VALUES ('{}', '{}', 'SQL', '{}', 'tauri-app', {}, true);",
                    version, description, filename, elapsed
                );
                let _ = run_psql(pg_bin_dir, &insert_sql, "unidocverse_db", "unidocverse")?;
                println!("  ✓ Migration {} applied ({}ms)", version, elapsed);
            }
            Err(err_msg) => {
                let elapsed = start_time.elapsed().as_millis() as u32;
                let insert_sql = format!(
                    "INSERT INTO public.flyway_schema_history (version, description, type, script, installed_by, execution_time, success) \
                     VALUES ('{}', '{}', 'SQL', '{}', 'tauri-app', {}, false);",
                    version, description, filename, elapsed
                );
                let _ = run_psql(pg_bin_dir, &insert_sql, "unidocverse_db", "unidocverse")?;
                return Err(format!("Migration {} failed: {}", version, err_msg));
            }
        }
    }
    
    Ok(())
}

// Helper: Check for system or portable Ollama and launch
fn ensure_ollama_started(resource_dir: &Path, data_models: &Path) {
    if TcpStream::connect("127.0.0.1:11434").is_ok() {
        println!("Ollama is already running.");
        return;
    }
    
    // 1. Try portable Ollama first
    let portable_ollama = resource_dir.join("ollama-portable").join("ollama");
    if portable_ollama.exists() {
        println!("Starting portable Ollama from: {:?}", portable_ollama);
        let mut cmd = Command::new(&portable_ollama);
        cmd.arg("serve");
        // Models bundled in the app (older Full builds), else the app's data folder, where the
        // built-in model is downloaded on demand (single installer)
        let bundled = resource_dir.join("ollama-portable").join("models");
        let models = if bundled.join("manifests").exists() { bundled } else { data_models.to_path_buf() };
        let _ = fs::create_dir_all(&models);
        cmd.env("OLLAMA_MODELS", models.to_str().unwrap());
        cmd.env("OLLAMA_HOST", "127.0.0.1:11434");
        cmd.env("OLLAMA_KEEP_ALIVE", "5m");
        cmd.env("OLLAMA_MAX_LOADED_MODELS", "1");
        cmd.env("OLLAMA_NUM_PARALLEL", "1");
        let _ = cmd.spawn();
        
        let start = Instant::now();
        while start.elapsed() < Duration::from_secs(5) {
            if TcpStream::connect("127.0.0.1:11434").is_ok() {
                println!("Portable Ollama started successfully!");
                return;
            }
            thread::sleep(Duration::from_millis(500));
        }
    }
    
    // 2. Fallback to system Ollama
    let paths = [
        "/opt/homebrew/bin/ollama",
        "/usr/local/bin/ollama",
        "/Applications/Ollama.app/Contents/Resources/ollama",
    ];
    
    for path in &paths {
        if Path::new(path).exists() {
            println!("Starting system Ollama from: {}", path);
            let _ = Command::new(path)
                .arg("serve")
                .spawn();
            
            let start = Instant::now();
            while start.elapsed() < Duration::from_secs(5) {
                if TcpStream::connect("127.0.0.1:11434").is_ok() {
                    println!("Ollama started successfully!");
                    return;
                }
                thread::sleep(Duration::from_millis(500));
            }
            break;
        }
    }
}

// Master service boot logic
fn init_and_start_services(app: &tauri::App) -> Result<(), String> {
    // Determine resources directory (handling dev fallback)
    let resource_dir = if cfg!(debug_assertions) {
        let current_dir = std::env::current_dir().unwrap();
        if current_dir.ends_with("src-tauri") {
            current_dir.join("resources")
        } else {
            current_dir.join("src-tauri").join("resources")
        }
    } else {
        app.path().resource_dir().map_err(|e| e.to_string())?.join("resources")
    };
    
    let app_data_dir = app.path().app_data_dir().map_err(|e| e.to_string())?;
    
    let pg_bin_target = app_data_dir.join("postgres-bin");
    let pg_data_dir = app_data_dir.join("postgres-data");
    let logs_dir = app_data_dir.join("logs");
    let uploads_dir = app_data_dir.join("uploads");
    
    // Ensure vital runtime directories exist
    fs::create_dir_all(&logs_dir).map_err(|e| e.to_string())?;
    fs::create_dir_all(&uploads_dir).map_err(|e| e.to_string())?;
    
    // 1. Ensure Postgres bin directory is extracted to app_data_dir (writable)
    if !pg_bin_target.join("bin").join(POSTGRES_BIN).exists() {
        println!("Preparing Postgres binaries...");
        
        #[cfg(target_arch = "aarch64")]
        let arch_folder = "postgres-arm64";
        #[cfg(not(target_arch = "aarch64"))]
        let arch_folder = "postgres-x64";
        
        let source_path = resource_dir.join(arch_folder);
        if !source_path.exists() {
            return Err(format!("Postgres source folder not found: {:?}", source_path));
        }
        
        copy_dir_all(&source_path, &pg_bin_target).map_err(|e| e.to_string())?;
        make_executable(&pg_bin_target).map_err(|e| e.to_string())?;
        println!("Postgres binaries ready!");
    }
    
    let pg_bin_dir = pg_bin_target.join("bin");
    
    // 2. Initialize Postgres database directory if missing
    if !pg_data_dir.join("PG_VERSION").exists() {
        println!("Initializing database directory...");
        fs::create_dir_all(&pg_data_dir).map_err(|e| e.to_string())?;
        
        let initdb_path = pg_bin_dir.join(INITDB_BIN);
        let status = Command::new(initdb_path)
            .args(&[
                "-D", pg_data_dir.to_str().unwrap(),
                "-U", "postgres",
                "--auth=trust",
                "--encoding=UTF8"
            ])
            .status()
            .map_err(|e| format!("Failed to run initdb: {}", e))?;
            
        if !status.success() {
            return Err("initdb failed".to_string());
        }
        
        // Append port configuration to postgresql.conf
        let pg_conf_path = pg_data_dir.join("postgresql.conf");
        let mut file = fs::OpenOptions::new()
            .append(true)
            .open(pg_conf_path)
            .map_err(|e| e.to_string())?;
            
        let lib_path = pg_bin_target.join("lib");
        writeln!(file, "\ndynamic_library_path = '{}:$libdir'\nlisten_addresses = 'localhost'\nport = 54321\n", lib_path.to_str().unwrap())
            .map_err(|e| e.to_string())?;
        println!("Database directory initialized!");
    }
    
    // 3. Start PostgreSQL
    println!("🐘 Starting PostgreSQL server...");
    let postgres_path = pg_bin_dir.join(POSTGRES_BIN);
    let pg_child = Command::new(postgres_path)
        .args(&[
            "-D", pg_data_dir.to_str().unwrap(),
            "-p", "54321"
        ])
        .spawn()
        .map_err(|e| format!("Failed to spawn postgres: {}", e))?;
        
    let state = app.state::<AppState>();
    *state.pg_child.lock().unwrap() = Some(pg_child);
    
    // Wait for PG port to open
    let start = Instant::now();
    let mut pg_ready = false;
    while start.elapsed() < Duration::from_secs(30) {
        if TcpStream::connect("127.0.0.1:54321").is_ok() {
            pg_ready = true;
            break;
        }
        thread::sleep(Duration::from_millis(500));
    }
    
    if !pg_ready {
        return Err("PostgreSQL startup timed out".to_string());
    }
    println!("PostgreSQL is ready!");
    
    // 4. Ensure Application User and Database
    let _ = run_psql(&pg_bin_dir, "CREATE ROLE unidocverse WITH SUPERUSER LOGIN PASSWORD 'unidocverse';", "postgres", "postgres");
    let _ = run_psql(&pg_bin_dir, "ALTER ROLE unidocverse WITH SUPERUSER;", "postgres", "postgres");
    
    // Create DB unidocverse_db
    let createdb_path = pg_bin_dir.join(CREATEDB_BIN);
    let _ = Command::new(createdb_path)
        .args(&[
            "-h", "localhost",
            "-p", "54321",
            "-U", "postgres",
            "-O", "unidocverse",
            "--encoding=UTF8",
            "unidocverse_db"
        ])
        .status();
        
    // Create pgvector extension
    let _ = run_psql(&pg_bin_dir, "CREATE EXTENSION IF NOT EXISTS vector;", "unidocverse_db", "postgres");
    
    // 5. Run SQL migrations
    let migrations_dir = resource_dir.join("migrations").join("sql");
    if migrations_dir.exists() {
        run_migrations(&pg_bin_dir, &migrations_dir)?;
    } else {
        println!("Migrations folder not found: {:?}", migrations_dir);
    }
    
    // 6. Start Ollama natively or portably
    ensure_ollama_started(&resource_dir, &app_data_dir.join("ollama-models"));
    
    // 6b. Bundled web search (SearxNG)
    *state.searx_child.lock().unwrap() = start_searxng(&resource_dir, &logs_dir);

    // 7. Start FastAPI application backend
    println!("🚀 Starting application backend...");
    let backend_path = resource_dir.join("backend").join(BACKEND_BIN);
    if !backend_path.exists() {
        return Err(format!("Backend executable not found at: {:?}", backend_path));
    }
    
    let mut backend_cmd = Command::new(&backend_path);
    backend_cmd.env("PYTHONUNBUFFERED", "1")
        .env("DATABASE_URL", "postgresql://unidocverse:unidocverse@localhost:54321/unidocverse_db")
        .env("PORT", "7979")
        .env("MODEL_PATH", resource_dir.join("models").join("all-mpnet-base-v2").to_str().unwrap())
        .env("RERANKER_PATH", resource_dir.join("models").join("bge-reranker-v2-m3").to_str().unwrap())
        .env("SEARXNG_URL", "http://localhost:8888")
        .env("OLLAMA_BASE_URL", "http://localhost:11434");
        
    // Starter edition: the reranker isn't bundled; the backend downloads it on first launch
    if let Ok(raw) = fs::read_to_string(resource_dir.join("starter.json")) {
        if let Ok(v) = serde_json::from_str::<serde_json::Value>(&raw) {
            if let (Some(url), Some(sha)) = (v["reranker_url"].as_str(), v["reranker_sha256"].as_str()) {
                backend_cmd.env("RERANKER_DOWNLOAD_URL", url)
                    .env("RERANKER_SHA256", sha)
                    .env("RERANKER_DOWNLOAD_DIR", app_data_dir.join("models").to_str().unwrap());
            }
            // Built-in answer model: downloaded only when the user picks it on Home
            if let (Some(url), Some(sha)) = (v["answer_url"].as_str(), v["answer_sha256"].as_str()) {
                backend_cmd.env("ANSWER_MODEL_URL", url)
                    .env("ANSWER_MODEL_SHA256", sha)
                    .env("ANSWER_MODEL_DIR", app_data_dir.join("ollama-models").to_str().unwrap())
                    .env("ANSWER_MODEL_NAME", v["answer_model"].as_str().unwrap_or("phi3:mini"));
            }
        }
    }

    let tesseract_dir = resource_dir.join("tesseract");
    if tesseract_dir.exists() {
        backend_cmd.env("TESSERACT_BINARY", tesseract_dir.join("bin").join("tesseract").to_str().unwrap())
            .env("TESSDATA_PREFIX", tesseract_dir.join("share").join("tessdata").to_str().unwrap());
    }
    let log_file_path = logs_dir.join("backend.log");
    let log_file = std::fs::File::create(&log_file_path)
        .map_err(|e| format!("Failed to create log file: {}", e))?;
    let stdio_out = std::process::Stdio::from(log_file.try_clone()
        .map_err(|e| format!("Failed to clone log file for stdout: {}", e))?);
    let stdio_err = std::process::Stdio::from(log_file);
    backend_cmd.stdout(stdio_out).stderr(stdio_err);
    
    let backend_child = backend_cmd.spawn()
        .map_err(|e| format!("Failed to spawn backend process: {}", e))?;
        
    *state.backend_child.lock().unwrap() = Some(backend_child);
    
    // Wait for backend port 7979 to open
    let start = Instant::now();
    let mut backend_ready = false;
    while start.elapsed() < Duration::from_secs(30) {
        if TcpStream::connect("127.0.0.1:7979").is_ok() {
            backend_ready = true;
            break;
        }
        thread::sleep(Duration::from_millis(500));
    }
    
    if !backend_ready {
        return Err("Application backend startup timed out".to_string());
    }
    println!("Backend server running successfully!");
    
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
  let app = tauri::Builder::default()
    .plugin(tauri_plugin_shell::init())
    .plugin(tauri_plugin_log::Builder::default()
      .level(log::LevelFilter::Info)
      .build())
    .manage(AppState {
      pg_child: std::sync::Mutex::new(None),
      backend_child: std::sync::Mutex::new(None),
      searx_child: std::sync::Mutex::new(None),
    })
    .invoke_handler(tauri::generate_handler![connect_mcp_client])
    .setup(|app| {
      // Start database and backend services synchronously
      if let Err(e) = init_and_start_services(app) {
        eprintln!("Fatal error during startup services check: {}", e);
        std::process::exit(1);
      }
      Ok(())
    })
    .build(tauri::generate_context!())
    .expect("error while building tauri application");

  app.run(|app_handle, event| {
    if let tauri::RunEvent::Exit = event {
      let state = app_handle.state::<AppState>();
      
      // Terminate PostgreSQL cleanly
      let pg_child = state.pg_child.lock().unwrap().take();
      if let Some(mut child) = pg_child {
        println!("Stopping PostgreSQL database process...");
        let _ = child.kill();
      }
      
      if let Some(mut child) = state.searx_child.lock().unwrap().take() {
        let _ = child.kill();
      }

      // Terminate backend server cleanly
      let backend_child = state.backend_child.lock().unwrap().take();
      if let Some(mut child) = backend_child {
        println!("Stopping application backend server...");
        let _ = child.kill();
      }
    }
  });
}

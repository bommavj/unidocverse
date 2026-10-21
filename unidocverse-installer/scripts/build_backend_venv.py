#!/usr/bin/env python3
"""
Build backend using the venv from unidocverse-service.
Supports compiling a Universal macOS binary (arm64 + x86_64) using Rosetta emulation.
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
SERVICE_DIR = ROOT_DIR.parent / "unidocverse-service"
VENV_PYTHON = SERVICE_DIR / "venv-arm64" / "bin" / "python"
VENV_PYINSTALLER = SERVICE_DIR / "venv-arm64" / "bin" / "pyinstaller"

VENV_X86_64_DIR = SERVICE_DIR / "venv_x86_64"
VENV_X86_64_PYTHON = VENV_X86_64_DIR / "bin" / "python"
VENV_X86_64_PYINSTALLER = VENV_X86_64_DIR / "bin" / "pyinstaller"

BACKEND_DIR = SERVICE_DIR
# UDV_LITE=1: Lite build (no PaddleOCR, no unused heavy packages) into its own folder
LITE = __import__("os").environ.get("UDV_LITE") == "1"
DIST_DIR = ROOT_DIR / ("backend-dist-lite" if LITE else "backend-dist")
_LITE_EXCLUDES = ", 'paddle', 'paddleocr', 'paddlex', 'shap', 'numba', 'llvmlite', 'googleapiclient'" if LITE else ""
SPEC_FILE = ROOT_DIR / "scripts" / "backend.spec"

def check_venv():
    """Verify venv exists and has PyInstaller"""
    if not VENV_PYTHON.exists():
        print(f"❌ Virtual environment not found at: {VENV_PYTHON}")
        print(f"   Run: cd {SERVICE_DIR} && python3 -m venv venv")
        sys.exit(1)
    
    print(f"✓ Using Python: {VENV_PYTHON}")
    
    # Install PyInstaller in venv if not present
    if not VENV_PYINSTALLER.exists():
        print("📦 Installing PyInstaller in venv...")
        subprocess.run(["uv", "pip", "install", "--python", str(VENV_PYTHON), "pyinstaller"], check=True)  # uv venv has no pip

def check_venv_x86_64():
    """Verify or create x86_64 venv under Rosetta (macOS only)"""
    if sys.platform != "darwin":
        return
    
    if VENV_X86_64_PYTHON.exists():
        try:
            # Check the Python version of the existing virtual environment
            res = subprocess.run(
                [str(VENV_X86_64_PYTHON), "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
                capture_output=True, text=True, check=True
            )
            version_str = res.stdout.strip()
            if version_str != "3.9":
                print(f"⚠️ Existing x86_64 venv uses Python {version_str}, but we need Python 3.9 (system python). Re-creating...")
                shutil.rmtree(VENV_X86_64_DIR)
        except Exception as e:
            print(f"⚠️ Error checking Python version in existing x86_64 venv: {e}. Re-creating...")
            shutil.rmtree(VENV_X86_64_DIR, ignore_errors=True)
            
    if not VENV_X86_64_PYTHON.exists():
        print(f"📦 Creating x86_64 virtual environment at: {VENV_X86_64_DIR}...")
        # We must use the universal system python explicitly: /usr/bin/python3 (which is Python 3.9.6)
        # and run under arch -x86_64
        cmd = ["arch", "-x86_64", "/usr/bin/python3", "-m", "venv", str(VENV_X86_64_DIR)]
        subprocess.run(cmd, check=True)
    
    # Install dependencies inside x86_64 venv
    print("📦 Ensuring dependencies are installed in x86_64 venv...")
    subprocess.run(["arch", "-x86_64", str(VENV_X86_64_PYTHON), "-m", "pip", "install", "--upgrade", "pip"], check=True)
    
    # Prepare x86_64 requirements
    req_file = SERVICE_DIR / "requirements.txt"
    req_x86_64 = SERVICE_DIR / "requirements_x86_64.txt"
    
    content = req_file.read_text()
    content = content.replace("torch==2.8.0", "torch==2.2.2")
    content = content.replace("torchvision>=0.19.0", "torchvision==0.17.2")
    content = content.replace("paddlepaddle==3.2.2", "paddlepaddle==3.0.0")
    # Pin cryptography to <44 to force the use of precompiled x86_64 wheels on macOS Python 3.9
    content += "\ncryptography<44\n"
    req_x86_64.write_text(content)
    
    try:
        subprocess.run(["arch", "-x86_64", str(VENV_X86_64_PYTHON), "-m", "pip", "install", "-r", str(req_x86_64), "--quiet"], check=True)
    finally:
        if req_x86_64.exists():
            req_x86_64.unlink()
    
    # Install PyInstaller in x86_64 venv if not present
    if not VENV_X86_64_PYINSTALLER.exists():
        subprocess.run(["arch", "-x86_64", str(VENV_X86_64_PYTHON), "-m", "pip", "install", "pyinstaller"], check=True)
        
    print("✓ x86_64 virtual environment ready!")

def clean_dist():
    """Clean previous build"""
    print("🧹 Cleaning previous builds...")
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(parents=True, exist_ok=True)

def find_main_py():
    """Find main.py"""
    main_py = BACKEND_DIR / "app" / "main.py"
    if not main_py.exists():
        raise FileNotFoundError(f"main.py not found at: {main_py}")
    print(f"✓ Found entry point: {main_py}")
    return main_py

def create_spec_file(main_py_path, onefile=False):
    """Create PyInstaller spec"""
    print(f"📝 Creating spec file (onefile={onefile})...")
    
    main_py_abs = str(main_py_path.resolve())
    app_dir_abs = str(main_py_path.parent.resolve())
    
    if onefile:
        spec_content = f'''# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules
import os as _os

# Libraries that import their own modules by name at runtime, which PyInstaller can't see.
# transformers keeps model code as .py source loaded on demand, and the build skips model folders
# it can't test-import (the reranker then failed: "No module named transformers.models.metaclip_2").
_dynamic = []
for _pkg in ('transformers', 'sentence_transformers'{"" if LITE else ", 'paddleocr'"}):
    try:
        _dynamic += collect_submodules(_pkg)
    except Exception:
        pass
_dynamic_data = []
try:
    import transformers as _tf
    _dynamic_data.append((_os.path.join(_os.path.dirname(_tf.__file__), 'models'), 'transformers/models'))
except Exception:
    pass
try:
    if {LITE!r}:
        raise ImportError('Lite build: no PaddleOCR')
    import paddleocr as _po
    _dynamic_data.append((_os.path.dirname(_po.__file__), 'paddleocr'))
except Exception:
    pass

block_cipher = None

a = Analysis(
    ['{main_py_abs}'],
    pathex=['{app_dir_abs}'],
    binaries=[],
    datas=[
        ('{app_dir_abs}', 'app'),
    ] + _dynamic_data,
    hiddenimports=[
        'uvicorn.logging',
        'uvicorn.loops.auto',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.http.h11_impl',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.protocols.websockets.wsproto_impl',
        'uvicorn.lifespan.on',
        'fastapi',
        'fastapi.routing',
        'fastapi.encoders',
        'starlette',
        'starlette.routing',
        'starlette.middleware',
        'starlette.middleware.cors',
        'pydantic',
        'pydantic_core',
        'pydantic_settings',
        'sqlalchemy',
        'sqlalchemy.ext.declarative',
        'sqlalchemy.dialects.postgresql',
        'psycopg2',
        'python_multipart',
        'langchain',
        'langchain_core',
        'langchain_community',
        'ollama',
    ] + _dynamic,
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=['matplotlib', 'tkinter', 'PyQt5'{_LITE_EXCLUDES}],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Never ship signing keys or issued licenses
a.datas = [d for d in a.datas if not (d[0].endswith('private_key.pem') or d[0].endswith('.udv.json') or 'research_cases.yaml' in d[0])]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='unidocverse-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
'''
    else:
        spec_content = f'''# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules
import os as _os

# Libraries that import their own modules by name at runtime, which PyInstaller can't see.
# transformers keeps model code as .py source loaded on demand, and the build skips model folders
# it can't test-import (the reranker then failed: "No module named transformers.models.metaclip_2").
_dynamic = []
for _pkg in ('transformers', 'sentence_transformers'{"" if LITE else ", 'paddleocr'"}):
    try:
        _dynamic += collect_submodules(_pkg)
    except Exception:
        pass
_dynamic_data = []
try:
    import transformers as _tf
    _dynamic_data.append((_os.path.join(_os.path.dirname(_tf.__file__), 'models'), 'transformers/models'))
except Exception:
    pass
try:
    if {LITE!r}:
        raise ImportError('Lite build: no PaddleOCR')
    import paddleocr as _po
    _dynamic_data.append((_os.path.dirname(_po.__file__), 'paddleocr'))
except Exception:
    pass

block_cipher = None

a = Analysis(
    ['{main_py_abs}'],
    pathex=['{app_dir_abs}'],
    binaries=[],
    datas=[
        ('{app_dir_abs}', 'app'),
    ] + _dynamic_data,
    hiddenimports=[
        'uvicorn.logging',
        'uvicorn.loops.auto',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.http.h11_impl',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.protocols.websockets.wsproto_impl',
        'uvicorn.lifespan.on',
        'fastapi',
        'fastapi.routing',
        'fastapi.encoders',
        'starlette',
        'starlette.routing',
        'starlette.middleware',
        'starlette.middleware.cors',
        'pydantic',
        'pydantic_core',
        'pydantic_settings',
        'sqlalchemy',
        'sqlalchemy.ext.declarative',
        'sqlalchemy.dialects.postgresql',
        'psycopg2',
        'python_multipart',
        'langchain',
        'langchain_core',
        'langchain_community',
        'ollama',
    ] + _dynamic,
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=['matplotlib', 'tkinter', 'PyQt5'{_LITE_EXCLUDES}],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Never ship signing keys or issued licenses
a.datas = [d for d in a.datas if not (d[0].endswith('private_key.pem') or d[0].endswith('.udv.json') or 'research_cases.yaml' in d[0])]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='unidocverse-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    target_arch=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name='unidocverse-backend',
)
'''
    
    SPEC_FILE.parent.mkdir(parents=True, exist_ok=True)
    SPEC_FILE.write_text(spec_content)
    print(f"✓ Spec file created: {SPEC_FILE}")

def build_slice(pyinstaller_bin, onefile, output_name, run_under_rosetta=False):
    """Build a single architecture slice"""
    print(f"🔨 Building backend slice {output_name}...")
    
    dist_slice = DIST_DIR / f"backend-{output_name}"
    if dist_slice.exists():
        shutil.rmtree(dist_slice)
    dist_slice.mkdir(parents=True, exist_ok=True)
    
    cmd = []
    if run_under_rosetta:
        cmd += ["arch", "-x86_64"]
        
    cmd += [
        str(pyinstaller_bin),
        "--clean",
        "--noconfirm",
        str(SPEC_FILE),
        "--distpath", str(dist_slice)
    ]
    
    print(f"   Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    print(f"✅ Slice {output_name} built successfully!")
    return dist_slice / "unidocverse-backend"

def build_backend_universal(main_py):
    """Build universal binary on macOS"""
    print("🔨 Starting macOS Universal build (arm64 + x86_64)...")
    
    # 1. Create spec file in one-file mode
    create_spec_file(main_py, onefile=True)
    
    # 2. Build ARM64 slice
    arm64_exe = build_slice(VENV_PYINSTALLER, onefile=True, output_name="arm64")
    
    # 3. Build x86_64 slice
    x86_64_exe = build_slice(VENV_X86_64_PYINSTALLER, onefile=True, output_name="x86_64", run_under_rosetta=True)
    
    # 4. Merge slices with lipo
    target_folder = DIST_DIR / "unidocverse-backend"
    if target_folder.exists():
        shutil.rmtree(target_folder)
    target_folder.mkdir(parents=True, exist_ok=True)
    
    target_exe = target_folder / "unidocverse-backend"
    
    print(f"🔗 Merging slices into a universal binary at: {target_exe}...")
    subprocess.run(["lipo", "-create", "-output", str(target_exe), str(arm64_exe), str(x86_64_exe)], check=True)
    print("✅ Slices successfully merged!")
    
    # Clean up temp slices folders
    shutil.rmtree(DIST_DIR / "backend-arm64", ignore_errors=True)
    shutil.rmtree(DIST_DIR / "backend-x86_64", ignore_errors=True)

def build_backend_standard(main_py):
    """Standard single-arch build"""
    print("🔨 Starting standard single-architecture build...")
    create_spec_file(main_py, onefile=False)
    
    cmd = [
        str(VENV_PYINSTALLER),
        "--clean",
        "--noconfirm",
        str(SPEC_FILE),
        "--distpath", str(DIST_DIR)
    ]
    
    print(f"   Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    print("✅ Backend built successfully!")

def verify_build():
    """Verify build and confirm universal binary"""
    exe_path = DIST_DIR / "unidocverse-backend" / "unidocverse-backend"
    if not exe_path.exists():
        raise FileNotFoundError(f"Executable not found: {exe_path}")
    
    size = exe_path.stat().st_size / (1024 * 1024)
    print(f"✓ Executable: {exe_path}")
    print(f"  Size: {size:.1f} MB")
    
    # Verify the binary contains both architectures
    result = subprocess.run(["lipo", "-info", str(exe_path)], capture_output=True, text=True)
    if result.returncode == 0:
        arch_info = result.stdout.strip()
        print(f"  Arch: {arch_info}")
        if "x86_64" in arch_info and "arm64" in arch_info:
            print("✅ Confirmed universal2 binary (arm64 + x86_64 — runs on ALL Macs!)")
        elif "arm64" in arch_info:
            print("⚠️  arm64 only — Intel Mac clients will get 'Bad CPU type' error!")
        elif "x86_64" in arch_info:
            print("⚠️  x86_64 only — Apple Silicon clients need Rosetta!")

def main():
    print("🚀 Building UniDocVerse Backend with venv")
    print("=" * 60)
    
    try:
        check_venv()
        # torch>=2.3 ships no Intel-Mac wheels, so universal is opt-in (UDV_UNIVERSAL=1)
        universal = sys.platform == "darwin" and os.environ.get("UDV_UNIVERSAL") == "1"
        if universal:
            check_venv_x86_64()
            
        main_py = find_main_py()
        clean_dist()
        
        if universal:
            build_backend_universal(main_py)
        else:
            build_backend_standard(main_py)
            
        verify_build()
        
        print("\n" + "=" * 60)
        print("✅ Build completed successfully!")
        print(f"📁 Output: {DIST_DIR / 'unidocverse-backend'}")
        print("\nTest it:")
        print(f"  export DATABASE_URL='postgresql://unidocverse:unidocverse@localhost:54320/unidocverse_db'")
        print(f"  {DIST_DIR / 'unidocverse-backend' / 'unidocverse-backend'}")
        
    except Exception as e:
        print(f"\n❌ Build failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
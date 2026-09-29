import os
import sys
from pathlib import Path
from typing import Optional, List

# Ensure package root is in sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from mcp.server.mcpserver import MCPServer
from core.config import config_mgr
from core.knowledge_db import knowledge_db
from core.builder import builder
from core.scaffolder import scaffolder

# Initialize MCP Server
app = MCPServer("zrx-developer")

@app.tool()
def zrx_status() -> dict:
    """
    Check the current ZRX-MCP configuration, detected SDK paths, supported CAD versions (2026/2025/2024/Nova),
    compiler availability (vcvarsall), and knowledge database document stats.
    """
    status = config_mgr.get_all_status()
    vcvars = config_mgr.find_vcvarsall()
    db_stats = knowledge_db.get_stats()
    return {
        "status": status,
        "vcvarsall_found": bool(vcvars),
        "vcvarsall_path": vcvars,
        "knowledge_db_stats": db_stats,
        "message": "ZRX-MCP is ready. SDK 2026 is fully active."
    }

@app.tool()
def search_zrx_docs(query: str, category: Optional[str] = None, version: Optional[str] = "2026", limit: int = 6) -> list:
    """
    Search the ZRX official documentation, API definitions, developer guides, and headers using full-text search (FTS5).
    Category can be 'guide', 'difference', 'migration', 'header', or None for all.
    """
    return knowledge_db.search(query=query, category=category, version=version, limit=limit)

@app.tool()
def get_known_differences(query: Optional[str] = None, limit: int = 6) -> list:
    """
    Query differences between AutoCAD ObjectARX and ZWCAD ZRX (crucial for avoiding API pitfalls and porting code).
    """
    return knowledge_db.get_known_differences(query=query, limit=limit)

@app.tool()
def search_sdk_samples(keyword: str, max_results: int = 6) -> list:
    """
    Search the official C++ and .NET sample projects in the local SDK for real, working code examples.
    """
    sdk_path = config_mgr.get_sdk_path("2026")
    if not sdk_path:
        return [{"error": "SDK path not available"}]
    
    samples_dir = sdk_path / "samples"
    if not samples_dir.exists():
        return [{"error": f"Samples directory not found in {sdk_path}"}]

    results = []
    kw_lower = keyword.lower()

    for p in samples_dir.rglob("*.cpp"):
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
            if kw_lower in content.lower() or kw_lower in p.name.lower():
                # Extract snippet
                idx = content.lower().find(kw_lower)
                start = max(0, idx - 150)
                end = min(len(content), idx + 450)
                snippet = content[start:end]
                results.append({
                    "file": str(p.relative_to(samples_dir)),
                    "snippet": snippet,
                    "full_path": str(p)
                })
                if len(results) >= max_results:
                    break
        except Exception:
            pass

    return results

@app.tool()
def scaffold_project(target_dir: str, project_name: str, project_type: str = "cpp", version: str = "2026", command_name: str = "MYCMD") -> dict:
    """
    Scaffold a new ZRX plugin project ready for headless/IDE-free development.
    project_type can be 'cpp' (C++ ZRX with hot-rebuild build.py) or 'dotnet' (.NET Framework 4.7 class library).
    """
    if project_type.lower() == "dotnet":
        return scaffolder.scaffold_dotnet_project(target_dir, project_name, version=version, command_name=command_name)
    return scaffolder.scaffold_cpp_project(target_dir, project_name, version=version, command_name=command_name)

@app.tool()
def build_plugin(project_dir: str, output_name: str = "plugin.zrx", version: str = "2026") -> dict:
    """
    Trigger a headless build of a ZRX plugin in project_dir without opening Visual Studio.
    Automatically prevents locked file errors by renaming locked .zrx files, compiles, and parses compiler errors.
    """
    return builder.build_project(project_dir=project_dir, output_name=output_name, version=version)

@app.tool()
def get_boilerplate(pattern_type: str, class_name: str = "MyEntity") -> str:
    """
    Generate standard, high-difficulty ZRX boilerplate code.
    pattern_type can be 'custom_entity' (ZcDbEntity), 'jig' (ZcEdJig), or 'transaction' (safe model-space append).
    """
    return scaffolder.generate_boilerplate(pattern_type=pattern_type, name=class_name)

if __name__ == "__main__":
    app.run(transport="stdio")

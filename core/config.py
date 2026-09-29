import os
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

CONFIG_FILE_PATH = Path(__file__).resolve().parent.parent / "config.json"

class ConfigManager:
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or CONFIG_FILE_PATH
        self.data: Dict[str, Any] = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        default_data = {
            "default_version": "2026",
            "versions": {
                "2026": {"name": "ZWCAD 2026", "sdk_path": r"D:\zwcad\ZRXSDK", "enabled": True},
                "2025": {"name": "ZWCAD 2025", "sdk_path": "", "enabled": False},
                "2024": {"name": "ZWCAD 2024", "sdk_path": "", "enabled": False},
                "nova": {"name": "ZWCAD Nova", "sdk_path": "", "enabled": False}
            },
            "build_defaults": {
                "vcvarsall_path": "",
                "fallback_vcvarsall_search": True,
                "hot_reload_rename": True
            }
        }
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    file_data = json.load(f)
                    default_data.update(file_data)
            except Exception as e:
                print(f"[WARN] Failed to read {self.config_path}: {e}")

        # Environment variable overrides
        env_map = {
            "2026": os.environ.get("ZRXSDK_2026"),
            "2025": os.environ.get("ZRXSDK_2025"),
            "2024": os.environ.get("ZRXSDK_2024"),
            "nova": os.environ.get("ZRXSDK_NOVA")
        }
        for ver, env_val in env_map.items():
            if env_val and ver in default_data["versions"]:
                default_data["versions"][ver]["sdk_path"] = env_val
                default_data["versions"][ver]["enabled"] = True

        env_default = os.environ.get("DEFAULT_ZRX_VERSION")
        if env_default and env_default in default_data["versions"]:
            default_data["default_version"] = env_default

        return default_data

    def get_version_info(self, version: Optional[str] = None) -> Dict[str, Any]:
        ver = version or self.data.get("default_version", "2026")
        if ver not in self.data["versions"]:
            ver = "2026"
        info = dict(self.data["versions"].get(ver, {}))
        info["version_key"] = ver
        return info

    def get_sdk_path(self, version: Optional[str] = None) -> Optional[Path]:
        info = self.get_version_info(version)
        path_str = info.get("sdk_path")
        if path_str:
            p = Path(path_str)
            if p.exists():
                return p
        return None

    def validate_sdk(self, version: Optional[str] = None) -> Dict[str, Any]:
        info = self.get_version_info(version)
        ver_key = info["version_key"]
        sdk_path = self.get_sdk_path(ver_key)

        if not sdk_path:
            # Check binary compatibility fallback
            fallback_ver = info.get("binary_compatible_with")
            if fallback_ver:
                fallback_path = self.get_sdk_path(fallback_ver)
                if fallback_path:
                    return {
                        "version": ver_key,
                        "valid": True,
                        "fallback": True,
                        "fallback_version": fallback_ver,
                        "sdk_path": str(fallback_path),
                        "message": f"Version {ver_key} is binary compatible with {fallback_ver}. Using {fallback_ver} SDK."
                    }
            return {
                "version": ver_key,
                "valid": False,
                "sdk_path": None,
                "message": f"SDK path for version {ver_key} is not configured or does not exist."
            }

        inc_path = sdk_path / "inc"
        lib_path = sdk_path / "lib-x64"
        samples_path = sdk_path / "samples"

        valid = inc_path.exists() and lib_path.exists()
        return {
            "version": ver_key,
            "valid": valid,
            "sdk_path": str(sdk_path),
            "inc_exists": inc_path.exists(),
            "lib_exists": lib_path.exists(),
            "samples_exists": samples_path.exists(),
            "message": "SDK verified." if valid else "SDK missing inc/ or lib-x64/ directory."
        }

    def get_all_status(self) -> Dict[str, Any]:
        status = {}
        for ver in self.data["versions"]:
            status[ver] = self.validate_sdk(ver)
        return {
            "default_version": self.data.get("default_version", "2026"),
            "versions": status
        }

    def find_vcvarsall(self) -> Optional[str]:
        cfg_path = self.data.get("build_defaults", {}).get("vcvarsall_path")
        if cfg_path and os.path.exists(cfg_path):
            return cfg_path

        candidates = [
            r"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat",
            r"C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvarsall.bat",
            r"C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvarsall.bat",
            r"C:\Program Files\Microsoft Visual Studio\2022\Enterprise\VC\Auxiliary\Build\vcvarsall.bat",
            r"C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Auxiliary\Build\vcvarsall.bat",
            r"C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvarsall.bat",
            r"C:\Program Files (x86)\Microsoft Visual Studio\2019\Professional\VC\Auxiliary\Build\vcvarsall.bat",
            r"C:\Program Files (x86)\Microsoft Visual Studio\2017\Community\VC\Auxiliary\Build\vcvarsall.bat",
        ]
        for c in candidates:
            if os.path.exists(c):
                return c

        # vswhere fallback
        vswhere = r"C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe"
        if os.path.exists(vswhere):
            try:
                cmd = f'"{vswhere}" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath'
                res = subprocess.check_output(cmd, shell=True, text=True).strip()
                if res:
                    vcvars = os.path.join(res, "VC", "Auxiliary", "Build", "vcvarsall.bat")
                    if os.path.exists(vcvars):
                        return vcvars
            except Exception:
                pass

        return None

config_mgr = ConfigManager()

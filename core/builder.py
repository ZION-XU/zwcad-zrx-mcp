import os
import sys
import time
import subprocess
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from .config import config_mgr

class ZrxBuilder:
    def __init__(self):
        pass

    def hot_unlock_file(self, target_path: Path) -> Optional[Path]:
        """
        If target .zrx is locked by a running ZWCAD process, rename it to .old so we can build a new one.
        Returns the old path if renamed, or None.
        """
        if not target_path.exists():
            return None
        try:
            target_path.unlink()
            return None
        except Exception:
            old_name = target_path.parent / f"{target_path.stem}_{int(time.time())}.zrx.old"
            try:
                target_path.rename(old_name)
                return old_name
            except Exception as e:
                print(f"[WARN] Failed to rename locked file {target_path}: {e}")
                return None

    def build_project(
        self,
        project_dir: str,
        sources: Optional[List[str]] = None,
        output_name: str = "plugin.zrx",
        def_file: Optional[str] = None,
        version: str = "2026",
        extra_includes: Optional[List[str]] = None,
        extra_libs: Optional[List[str]] = None,
        use_qt: bool = False,
        qt_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Headless CLI direct build for ZRX plugins without opening Visual Studio.
        """
        proj_p = Path(project_dir)
        if not proj_p.exists():
            return {"success": False, "message": f"Project directory does not exist: {project_dir}"}

        # Check for existing build.py in project dir
        custom_build_py = proj_p / "build.py"
        if custom_build_py.exists():
            # Run the project's own build.py
            cmd = f'python "{custom_build_py}"'
            proc = subprocess.run(cmd, cwd=str(proj_p), shell=True, capture_output=True, text=True)
            success = proc.returncode == 0
            errors = self._parse_compiler_errors(proc.stdout + "\n" + proc.stderr)
            return {
                "success": success,
                "mode": "custom_build_py",
                "returncode": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "errors": errors,
                "message": "Build finished via custom build.py" if success else "Build failed!"
            }

        # Otherwise perform standard compilation
        vcvarsall = config_mgr.find_vcvarsall()
        if not vcvarsall:
            return {"success": False, "message": "Cannot find vcvarsall.bat. Please configure vcvarsall_path in config.json."}

        sdk_path = config_mgr.get_sdk_path(version)
        if not sdk_path:
            return {"success": False, "message": f"SDK path for version {version} not found."}

        out_path = proj_p / output_name
        renamed_old = self.hot_unlock_file(out_path)

        inc_dirs = [
            str(sdk_path / "inc"),
            str(sdk_path / "arxport" / "inc-x64"),
            str(sdk_path / "arxport" / "inc"),
        ]
        if extra_includes:
            inc_dirs.extend(extra_includes)

        lib_dirs = [
            str(sdk_path / "lib-x64")
        ]

        # Discover source files if not specified
        if not sources:
            sources = [f.name for f in proj_p.glob("*.cpp")]
        if not sources:
            return {"success": False, "message": "No C++ source files (*.cpp) found in project directory."}

        # Standard ZRX libs
        core_libs = [
            "ZWCAD.lib", "ZwAuto.lib", "ZwZrx.lib", "ZwDatabase.lib", 
            "ZwRx.lib", "ZwGeometry.lib", "ZwdUI.lib", "ZwUI.lib", 
            "ZwBase.lib", "ZwGs.lib", "ZwPAL.lib", "ZwTc.lib",
            "user32.lib", "kernel32.lib", "gdi32.lib", "shell32.lib"
        ]
        if extra_libs:
            core_libs.extend(extra_libs)

        inc_flags = " ".join([f'/I"{d}"' for d in inc_dirs if os.path.exists(d)])
        lib_flags = " ".join([f'/LIBPATH:"{d}"' for d in lib_dirs if os.path.exists(d)])
        libs_str = " ".join(core_libs)
        src_str = " ".join(sources)

        def_flag = f"/DEF:{def_file}" if def_file and (proj_p / def_file).exists() else ""
        if not def_flag:
            default_def = proj_p / f"{out_path.stem}.def"
            if default_def.exists():
                def_flag = f"/DEF:{default_def.name}"

        compile_cmd = (
            f'call "{vcvarsall}" x64 && '
            f'cl /nologo /utf-8 /O2 /MD /EHsc /D_AFXDLL /DUNICODE /D_UNICODE /DWIN32 /D_WINDOWS /D_USRDLL /D_WIN32_WINNT=0x0600 '
            f'{inc_flags} /c {src_str} && '
            f'link /nologo /DLL {def_flag} /OUT:"{output_name}" {lib_flags} *.obj {libs_str}'
        )

        proc = subprocess.run(compile_cmd, cwd=str(proj_p), shell=True, capture_output=True, text=True)
        success = proc.returncode == 0
        all_output = proc.stdout + "\n" + proc.stderr
        errors = self._parse_compiler_errors(all_output)

        return {
            "success": success,
            "mode": "standard_cl_link",
            "output_file": str(out_path) if success else None,
            "locked_file_renamed": str(renamed_old) if renamed_old else None,
            "returncode": proc.returncode,
            "errors": errors,
            "raw_output": all_output,
            "message": "Build SUCCESS" if success else f"Build FAILED with {len(errors)} detected error(s)."
        }

    def _parse_compiler_errors(self, log: str) -> List[Dict[str, str]]:
        errors = []
        # Pattern for cl errors: file(line): error Cxxxx: message
        cl_pattern = re.compile(r'([a-zA-Z0-9_\-\.\\]+\([0-9]+\))\s*:\s*(error\s+[A-Z0-9]+)\s*:\s*(.*)')
        # Pattern for link errors: error LNKxxxx: message
        lnk_pattern = re.compile(r'(error\s+LNK[0-9]+)\s*:\s*(.*)')

        for line in log.splitlines():
            line = line.strip()
            cl_m = cl_pattern.search(line)
            if cl_m:
                errors.append({
                    "location": cl_m.group(1),
                    "code": cl_m.group(2),
                    "message": cl_m.group(3)
                })
                continue
            lnk_m = lnk_pattern.search(line)
            if lnk_m:
                errors.append({
                    "location": "linker",
                    "code": lnk_m.group(1),
                    "message": lnk_m.group(2)
                })
        return errors

builder = ZrxBuilder()

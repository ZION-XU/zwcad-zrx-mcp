import os
import sys
import time
import shutil
import subprocess
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup

from .config import config_mgr
from .knowledge_db import knowledge_db

SEVEN_ZIP_PATH = r"C:\Program Files\7-Zip\7z.exe"
DEFAULT_DOCS_DIR = Path(r"D:\zwcad\zrx-document")

class SdkExtractor:
    def __init__(self, temp_dir: Optional[Path] = None):
        self.temp_dir = temp_dir or (Path(__file__).resolve().parent.parent / "temp_extract")

    def decompile_chm(self, chm_path: Path, out_dir: Path) -> bool:
        if not chm_path or not chm_path.exists():
            print(f"[WARN] CHM not found: {chm_path}")
            return False
        out_dir.mkdir(parents=True, exist_ok=True)
        
        # Priority 1: 7-Zip
        if os.path.exists(SEVEN_ZIP_PATH):
            try:
                cmd = f'"{SEVEN_ZIP_PATH}" x "{str(chm_path)}" "-o{str(out_dir)}" -r -y'
                res = subprocess.run(cmd, shell=True, capture_output=True)
                if res.returncode == 0:
                    time.sleep(0.2)
                    return True
            except Exception as e:
                print(f"[WARN] 7-Zip extraction failed for {chm_path.name}: {e}")

        # Priority 2: Windows hh.exe
        try:
            cmd = f'hh.exe -decompile "{str(out_dir)}" "{str(chm_path)}"'
            subprocess.run(cmd, shell=True, capture_output=True, text=True)
            time.sleep(0.5)
            return True
        except Exception as e:
            print(f"[ERROR] Failed to decompile {chm_path}: {e}")
            return False

    def extract_text_from_html(self, html_path: Path) -> Optional[Dict[str, str]]:
        try:
            raw = html_path.read_bytes()
            if not raw or len(raw) < 10:
                return None

            # Detect charset from meta tag
            charset_match = re.search(rb'charset\s*=\s*["\']?([a-zA-Z0-9_\-]+)', raw[:2048], re.IGNORECASE)
            detected_enc = charset_match.group(1).decode("ascii", errors="ignore").lower() if charset_match else None

            candidates = []
            if detected_enc in ["gb2312", "gbk", "gb18030"]:
                candidates = ["gb18030", "utf-8", "latin-1"]
            elif detected_enc in ["utf-8", "utf8"]:
                candidates = ["utf-8", "gb18030", "latin-1"]
            else:
                candidates = ["gb18030", "utf-8", "latin-1"]

            content = None
            for enc in candidates:
                try:
                    content = raw.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue

            if not content:
                return None

            soup = BeautifulSoup(content, "html.parser")
            for s in soup(["script", "style"]):
                s.extract()

            title = soup.title.string.strip() if soup.title and soup.title.string else html_path.stem
            title = re.sub(r'[\r\n\t]+', ' ', title).strip()

            text = soup.get_text(separator="\n")
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            clean_text = "\n".join(lines)

            if len(clean_text) < 30:
                return None

            return {
                "title": title,
                "content": clean_text
            }
        except Exception:
            return None

    def _find_doc_file(self, filename: str, fallback_sdk_subpath: Optional[str] = None) -> Optional[Path]:
        # 1. Search D:\zwcad\zrx-document
        p1 = DEFAULT_DOCS_DIR / filename
        if p1.exists():
            return p1

        # 2. Search SDK path if configured
        if fallback_sdk_subpath:
            sdk_path = config_mgr.get_sdk_path("2026")
            if sdk_path:
                p2 = sdk_path / fallback_sdk_subpath
                if p2.exists():
                    return p2
        return None

    def index_known_differences(self, version: str = "2026"):
        chm = self._find_doc_file("KnownDifferences.chm", "Doc/KnownDifferences.chm")
        if not chm:
            print("[WARN] KnownDifferences.chm not found.")
            return

        print(f"Indexing KnownDifferences from {chm} ...")
        out_dir = self.temp_dir / "known_diff"
        if self.decompile_chm(chm, out_dir):
            docs = []
            for html_file in out_dir.rglob("*.htm*"):
                parsed = self.extract_text_from_html(html_file)
                if parsed:
                    docs.append({
                        "version": version,
                        "category": "difference",
                        "title": parsed["title"],
                        "symbol": "",
                        "content": parsed["content"],
                        "url_or_path": f"KnownDifferences/{html_file.name}"
                    })
            if docs:
                knowledge_db.add_docs_batch(docs)
                print(f"Added {len(docs)} KnownDifferences documents.")

    def index_guide_chs_2026(self, version: str = "2026"):
        chm = self._find_doc_file("ZWCAD_ZRX_Guide_chs_2026.chm", "ZWCAD_ZRX_Guide_chs_2026.chm")
        if not chm:
            print("[WARN] ZWCAD_ZRX_Guide_chs_2026.chm not found.")
            return

        print(f"Indexing ZRX Guide 2026 (CHS) from {chm} ...")
        out_dir = self.temp_dir / "guide_chs_2026"
        if self.decompile_chm(chm, out_dir):
            docs = []
            for html_file in out_dir.rglob("*.htm*"):
                parsed = self.extract_text_from_html(html_file)
                if parsed:
                    docs.append({
                        "version": version,
                        "category": "guide",
                        "title": parsed["title"],
                        "symbol": "",
                        "content": parsed["content"],
                        "url_or_path": f"Guide_CHS_2026/{html_file.name}"
                    })
            if docs:
                knowledge_db.add_docs_batch(docs)
                print(f"Added {len(docs)} ZRX Guide 2026 (CHS) documents.")

    def index_migration_chs_2026(self, version: str = "2026"):
        chm = self._find_doc_file("ZWCAD_ZRX_Migration_chs_2026.chm", "Doc/ZRX_Migration_Manual.chm")
        if not chm:
            print("[WARN] ZWCAD_ZRX_Migration_chs_2026.chm not found.")
            return

        print(f"Indexing ZRX Migration 2026 (CHS) from {chm} ...")
        out_dir = self.temp_dir / "migration_chs_2026"
        if self.decompile_chm(chm, out_dir):
            docs = []
            for html_file in out_dir.rglob("*.htm*"):
                parsed = self.extract_text_from_html(html_file)
                if parsed:
                    docs.append({
                        "version": version,
                        "category": "migration",
                        "title": parsed["title"],
                        "symbol": "",
                        "content": parsed["content"],
                        "url_or_path": f"Migration_CHS_2026/{html_file.name}"
                    })
            if docs:
                knowledge_db.add_docs_batch(docs)
                print(f"Added {len(docs)} Migration 2026 (CHS) documents.")

    def index_migration_chs_2025(self, version: str = "2025"):
        chm = self._find_doc_file("ZWCAD_ZRX_Migration_Manual_chs_2025.chm")
        if not chm:
            print("[WARN] ZWCAD_ZRX_Migration_Manual_chs_2025.chm not found.")
            return

        print(f"Indexing ZRX Migration 2025 (CHS) from {chm} ...")
        out_dir = self.temp_dir / "migration_chs_2025"
        if self.decompile_chm(chm, out_dir):
            docs = []
            for html_file in out_dir.rglob("*.htm*"):
                parsed = self.extract_text_from_html(html_file)
                if parsed:
                    docs.append({
                        "version": version,
                        "category": "migration",
                        "title": parsed["title"],
                        "symbol": "",
                        "content": parsed["content"],
                        "url_or_path": f"Migration_CHS_2025/{html_file.name}"
                    })
            if docs:
                knowledge_db.add_docs_batch(docs)
                print(f"Added {len(docs)} Migration 2025 (CHS) documents.")

    def index_guide_enu_2025(self, version: str = "2025"):
        chm = self._find_doc_file("ZWCAD_ZRXDev_enu_2025.chm")
        if not chm:
            print("[WARN] ZWCAD_ZRXDev_enu_2025.chm not found.")
            return

        print(f"Indexing ZRX Developer Guide 2025 (ENU) from {chm} ...")
        out_dir = self.temp_dir / "guide_enu_2025"
        if self.decompile_chm(chm, out_dir):
            docs = []
            for html_file in out_dir.rglob("*.htm*"):
                parsed = self.extract_text_from_html(html_file)
                if parsed:
                    docs.append({
                        "version": version,
                        "category": "guide",
                        "title": parsed["title"],
                        "symbol": "",
                        "content": parsed["content"],
                        "url_or_path": f"Guide_ENU_2025/{html_file.name}"
                    })
            if docs:
                knowledge_db.add_docs_batch(docs)
                print(f"Added {len(docs)} Developer Guide 2025 (ENU) documents.")

    def index_headers(self, version: str = "all"):
        sdk_path = config_mgr.get_sdk_path("2026")
        if not sdk_path:
            return
        inc_dir = sdk_path / "inc"
        if not inc_dir.exists():
            return

        print(f"Indexing C++ headers from {inc_dir} (version={version}) ...")
        docs = []
        class_regex = re.compile(r'class\s+([A-Z0-9_]+)\s*([A-Za-z0-9_]+)?\s*:\s*public\s+([A-Za-z0-9_]+)', re.IGNORECASE)

        for h_file in inc_dir.glob("*.h"):
            try:
                content = h_file.read_text(encoding="utf-8", errors="ignore")
                classes = []
                for m in class_regex.finditer(content):
                    cname = m.group(2) if m.group(2) else m.group(1)
                    if cname and not cname.startswith("ZSOFT"):
                        classes.append(cname)

                # Store header summary
                if classes or len(content) > 500:
                    summary = f"Header: {h_file.name}\nClasses defined: {', '.join(classes[:15])}\n"
                    docs.append({
                        "version": version,
                        "category": "header",
                        "title": f"Header {h_file.name}",
                        "symbol": ", ".join(classes[:5]),
                        "content": summary + "\n" + content[:2500],
                        "url_or_path": str(h_file)
                    })
            except Exception:
                pass

        if docs:
            knowledge_db.add_docs_batch(docs)
            print(f"Added {len(docs)} Header index documents.")

    def cleanup(self):
        if self.temp_dir.exists():
            try:
                shutil.rmtree(self.temp_dir, ignore_errors=True)
            except Exception:
                pass

extractor = SdkExtractor()

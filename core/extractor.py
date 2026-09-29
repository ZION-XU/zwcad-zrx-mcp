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

class SdkExtractor:
    def __init__(self, temp_dir: Optional[Path] = None):
        self.temp_dir = temp_dir or (Path(__file__).resolve().parent.parent / "temp_extract")

    def decompile_chm(self, chm_path: Path, out_dir: Path) -> bool:
        if not chm_path.exists():
            return False
        out_dir.mkdir(parents=True, exist_ok=True)
        try:
            cmd = f'hh.exe -decompile {str(out_dir)} {str(chm_path)}'
            subprocess.run(cmd, shell=True, capture_output=True, text=True)
            # Small wait to ensure filesystem flush
            time.sleep(0.3)
            return True
        except Exception as e:
            print(f"[ERROR] Failed to decompile {chm_path}: {e}")
            return False

    def extract_text_from_html(self, html_path: Path) -> Optional[Dict[str, str]]:
        try:
            content = None
            for enc in ["utf-8", "gb18030", "gb2312", "latin-1"]:
                try:
                    with open(html_path, "r", encoding=enc) as f:
                        content = f.read()
                    break
                except UnicodeDecodeError:
                    continue
            if not content:
                return None
            soup = BeautifulSoup(content, "html.parser")
            
            # Remove scripts and styles
            for s in soup(["script", "style"]):
                s.extract()

            title = soup.title.string.strip() if soup.title and soup.title.string else html_path.stem
            
            # Get text
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

    def index_known_differences(self, version: str = "2026"):
        sdk_path = config_mgr.get_sdk_path(version)
        if not sdk_path:
            return
        chm = sdk_path / "Doc" / "KnownDifferences.chm"
        if not chm.exists():
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

    def index_guide_chs(self, version: str = "2026"):
        sdk_path = config_mgr.get_sdk_path(version)
        if not sdk_path:
            return
        chm = sdk_path / "ZWCAD_ZRX_Guide_chs_2026.chm"
        if not chm.exists():
            # Check root doc folder
            alt_chm = Path(r"D:\zwcad\zrx-document\ZWCAD_ZRX_Guide_chs_2026.chm")
            if alt_chm.exists():
                chm = alt_chm
            else:
                return

        print(f"Indexing ZRX Guide (CHS) from {chm} ...")
        out_dir = self.temp_dir / "guide_chs"
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
                        "url_or_path": f"Guide_CHS/{html_file.name}"
                    })
            if docs:
                knowledge_db.add_docs_batch(docs)
                print(f"Added {len(docs)} ZRX Guide (CHS) documents.")

    def index_migration_manual(self, version: str = "2026"):
        sdk_path = config_mgr.get_sdk_path(version)
        if not sdk_path:
            return
        chm = sdk_path / "Doc" / "ZRX_Migration_Manual.chm"
        if not chm.exists():
            return

        print(f"Indexing ZRX Migration Manual from {chm} ...")
        out_dir = self.temp_dir / "migration"
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
                        "url_or_path": f"Migration/{html_file.name}"
                    })
            if docs:
                knowledge_db.add_docs_batch(docs)
                print(f"Added {len(docs)} Migration documents.")

    def index_headers(self, version: str = "2026"):
        sdk_path = config_mgr.get_sdk_path(version)
        if not sdk_path:
            return
        inc_dir = sdk_path / "inc"
        if not inc_dir.exists():
            return

        print(f"Indexing C++ headers from {inc_dir} ...")
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
            shutil.rmtree(self.temp_dir, ignore_errors=True)

extractor = SdkExtractor()

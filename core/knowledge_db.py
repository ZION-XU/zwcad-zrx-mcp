import sqlite3
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "knowledge.db"

class KnowledgeDB:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS docs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version TEXT NOT NULL,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                symbol TEXT,
                content TEXT NOT NULL,
                url_or_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_docs_symbol ON docs(symbol);
            """)
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_docs_version_category ON docs(version, category);
            """)
            
            # FTS5 Virtual Table
            cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(
                title,
                symbol,
                content,
                category,
                version,
                content='docs',
                content_rowid='id',
                tokenize='unicode61'
            )
            """)

            # Triggers to keep FTS in sync with docs table
            cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS docs_ai AFTER INSERT ON docs BEGIN
                INSERT INTO docs_fts(rowid, title, symbol, content, category, version)
                VALUES (new.id, new.title, new.symbol, new.content, new.category, new.version);
            END;
            """)
            cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS docs_ad AFTER DELETE ON docs BEGIN
                INSERT INTO docs_fts(docs_fts, rowid, title, symbol, content, category, version)
                VALUES('delete', old.id, old.title, old.symbol, old.content, old.category, old.version);
            END;
            """)
            cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS docs_au AFTER UPDATE ON docs BEGIN
                INSERT INTO docs_fts(docs_fts, rowid, title, symbol, content, category, version)
                VALUES('delete', old.id, old.title, old.symbol, old.content, old.category, old.version);
                INSERT INTO docs_fts(rowid, title, symbol, content, category, version)
                VALUES (new.id, new.title, new.symbol, new.content, new.category, new.version);
            END;
            """)
            conn.commit()

    def add_doc(self, version: str, category: str, title: str, symbol: Optional[str], content: str, url_or_path: str = "") -> int:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO docs (version, category, title, symbol, content, url_or_path) VALUES (?, ?, ?, ?, ?, ?)",
                (version, category, title, symbol or "", content, url_or_path)
            )
            conn.commit()
            return cursor.lastrowid

    def add_docs_batch(self, docs_list: List[Dict[str, Any]]):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            for doc in docs_list:
                cursor.execute(
                    "INSERT INTO docs (version, category, title, symbol, content, url_or_path) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        doc.get("version", "2026"),
                        doc.get("category", "general"),
                        doc.get("title", ""),
                        doc.get("symbol", ""),
                        doc.get("content", ""),
                        doc.get("url_or_path", "")
                    )
                )
            conn.commit()

    def search(self, query: str, category: Optional[str] = None, version: Optional[str] = None, limit: int = 8) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cleaned_query = re.sub(r'[^\w\s]', ' ', query).strip()
            if not cleaned_query:
                return []
            
            terms = cleaned_query.split()
            fts_query = " OR ".join(f'"{t}"' for t in terms)

            sql = """
            SELECT docs.id, docs.version, docs.category, docs.title, docs.symbol, 
                   docs.content, docs.url_or_path, rank
            FROM docs_fts
            JOIN docs ON docs_fts.rowid = docs.id
            WHERE docs_fts MATCH ?
            """
            params: List[Any] = [fts_query]

            if category:
                sql += " AND docs.category = ?"
                params.append(category)

            if version:
                sql += " AND (docs.version = ? OR docs.version = 'all')"
                params.append(version)

            sql += " ORDER BY rank LIMIT ?"
            params.append(limit)

            try:
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                results = []
                for r in rows:
                    results.append({
                        "id": r["id"],
                        "version": r["version"],
                        "category": r["category"],
                        "title": r["title"],
                        "symbol": r["symbol"],
                        "snippet": r["content"][:600] + ("..." if len(r["content"]) > 600 else ""),
                        "url_or_path": r["url_or_path"],
                        "rank": r["rank"]
                    })
                return results
            except Exception as e:
                print(f"[ERROR] search failed: {e}")
                return []

    def get_symbol_exact(self, symbol: str, version: Optional[str] = None) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            sql = "SELECT * FROM docs WHERE (symbol = ? OR title = ?)"
            params: List[Any] = [symbol, symbol]
            if version:
                sql += " AND (version = ? OR version = 'all')"
                params.append(version)
            sql += " ORDER BY id DESC LIMIT 1"
            cursor.execute(sql, params)
            r = cursor.fetchone()
            if r:
                return dict(r)
            return None

    def get_known_differences(self, query: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        if query:
            return self.search(query=query, category="difference", limit=limit)
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM docs WHERE category = 'difference' LIMIT ?", (limit,))
            return [dict(r) for r in cursor.fetchall()]

    def get_stats(self) -> Dict[str, Any]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT count(*) as total FROM docs")
            total = cursor.fetchone()["total"]

            cursor.execute("SELECT category, count(*) as cnt FROM docs GROUP BY category")
            categories = {r["category"]: r["cnt"] for r in cursor.fetchall()}

            cursor.execute("SELECT version, count(*) as cnt FROM docs GROUP BY version")
            versions = {r["version"]: r["cnt"] for r in cursor.fetchall()}

            return {
                "total_documents": total,
                "categories": categories,
                "versions": versions
            }

    def clear(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM docs")
            cursor.execute("DELETE FROM docs_fts")
            conn.commit()

knowledge_db = KnowledgeDB()

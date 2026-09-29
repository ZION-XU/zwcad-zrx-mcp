import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.extractor import extractor
from core.knowledge_db import knowledge_db

def main():
    print("=== Starting ZRX SDK Knowledge Base Indexing ===")
    knowledge_db.clear()
    
    # 1. Known differences
    extractor.index_known_differences(version="2026")

    # 2. Chinese Guide 2026
    extractor.index_guide_chs(version="2026")

    # 3. Migration manual
    extractor.index_migration_manual(version="2026")

    # 4. Header index
    extractor.index_headers(version="2026")

    extractor.cleanup()

    stats = knowledge_db.get_stats()
    print("=== Indexing Completed ===")
    print("Knowledge DB Stats:", stats)

if __name__ == "__main__":
    main()

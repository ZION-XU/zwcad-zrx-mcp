import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.extractor import extractor
from core.knowledge_db import knowledge_db

def main():
    print("==================================================")
    print("=== Starting ZRX Multi-Version Knowledge Base Indexing ===")
    print("==================================================")
    knowledge_db.clear()

    # 1. 2026 Known differences (AutoCAD vs ZRX)
    extractor.index_known_differences(version="2026")

    # 2. 2026 Chinese Developer Guide (ZWCAD_ZRX_Guide_chs_2026.chm)
    extractor.index_guide_chs_2026(version="2026")

    # 3. 2026 Chinese Migration Manual (ZWCAD_ZRX_Migration_chs_2026.chm)
    extractor.index_migration_chs_2026(version="2026")

    # 4. 2025 Chinese Migration Manual (ZWCAD_ZRX_Migration_Manual_chs_2025.chm)
    extractor.index_migration_chs_2025(version="2025")

    # 5. 2025 Developer Guide (ZWCAD_ZRXDev_enu_2025.chm)
    extractor.index_guide_enu_2025(version="2025")

    # 6. C++ Headers (Universal 'all' for 2025 & 2026 binary compatibility)
    extractor.index_headers(version="all")

    # Cleanup temp extracted files
    extractor.cleanup()

    stats = knowledge_db.get_stats()
    print("==================================================")
    print("=== Indexing Completed Successfully ===")
    print("==================================================")
    print("Knowledge DB Stats:", stats)

if __name__ == "__main__":
    main()

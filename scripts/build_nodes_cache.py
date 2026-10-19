# parse the pdf once at build time and save data/processed/nodes.json

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modeling.build_nodes import build_nodes
from modeling.nodes_cache import save_nodes

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PDF_PATH = PROJECT_ROOT / "data" / "raw" / "updated dam file.pdf"
CACHE_PATH = PROJECT_ROOT / "data" / "processed" / "nodes.json"

if __name__ == "__main__":
    nodes = build_nodes(str(PDF_PATH))
    save_nodes(nodes, CACHE_PATH)
    print(f"Cached {len(nodes)} nodes to {CACHE_PATH}")

"""
Pre-parses the DAM PDF once and caches the result to
data/processed/nodes.json. Run manually after data/raw/ changes, or
automatically at Docker build time (see Dockerfile).

Why this exists: modeling.build_nodes.build_nodes() opens the raw PDF
with pdfplumber and does word- and character-level extraction across
every page - real work, and real memory (pdfplumber/pdfminer cache
font and page resources as they go). Running that fresh on every
single process boot was fine on a dev machine, but was enough to
OOM-kill the container on Render's 512MB free instance before it ever
opened a port (2026-08-06, see docs/decisions.md). Baking a pre-built
cache into the image means the deployed process never imports
pdfplumber's heavy path at request time at all - it just loads a small
JSON file in webapp/backend.py's startup event.
"""

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

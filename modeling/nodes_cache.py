import json
from pathlib import Path

from schema.schema import Node

# has_children/actions are @computed_field on Node - always derivable
# from children/responsibilities, so caching them would just be dead
# weight on disk and Node recomputes them for free the moment
# load_nodes() reconstructs each one.
_COMPUTED_FIELDS = {"has_children", "actions"}


def save_nodes(nodes, cache_path):
    """
    Serializes {id: Node} to a single JSON file at cache_path.
    """
    cache_path = Path(cache_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        node_id: node.model_dump(exclude=_COMPUTED_FIELDS)
        for node_id, node in nodes.items()
    }
    cache_path.write_text(json.dumps(data))


def load_nodes(cache_path):
    """Reconstructs {id: Node} from a file written by save_nodes()."""
    data = json.loads(Path(cache_path).read_text())
    return {node_id: Node(**node_data) for node_id, node_data in data.items()}

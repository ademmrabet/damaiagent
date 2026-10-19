import json
from pathlib import Path

from schema.schema import Node

_COMPUTED_FIELDS = {"has_children", "actions"}


# write the nodes to a json cache file
def save_nodes(nodes, cache_path):
    cache_path = Path(cache_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        node_id: node.model_dump(exclude=_COMPUTED_FIELDS)
        for node_id, node in nodes.items()
    }
    cache_path.write_text(json.dumps(data))


# read the nodes back from the json cache
def load_nodes(cache_path):
    data = json.loads(Path(cache_path).read_text())
    return {node_id: Node(**node_data) for node_id, node_data in data.items()}

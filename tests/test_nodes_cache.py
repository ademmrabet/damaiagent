import pytest

from modeling.build_nodes import build_nodes
from modeling.nodes_cache import load_nodes, save_nodes
from tests.fixtures.known_cases import PDF_PATH


@pytest.fixture(scope="module")
def live_nodes():
    return build_nodes(PDF_PATH)


def test_save_then_load_round_trips_losslessly(tmp_path, live_nodes):
    cache_path = tmp_path / "nodes.json"
    save_nodes(live_nodes, cache_path)
    reloaded = load_nodes(cache_path)

    assert set(reloaded.keys()) == set(live_nodes.keys())
    for node_id, node in live_nodes.items():
        assert reloaded[node_id].model_dump() == node.model_dump()


def test_computed_fields_are_not_persisted_to_disk(tmp_path, live_nodes):
    # has_children/actions are @computed_field on Node - real work if
    # they silently doubled the file size for no reason, since they're
    # 100% derivable from children/responsibilities and load_nodes()
    # recomputes them for free the moment each Node is reconstructed.
    import json

    cache_path = tmp_path / "nodes.json"
    save_nodes(live_nodes, cache_path)
    raw = json.loads(cache_path.read_text())

    sample_id = next(iter(raw))
    assert "has_children" not in raw[sample_id]
    assert "actions" not in raw[sample_id]

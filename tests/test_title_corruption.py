import pytest

from modeling.build_nodes import build_nodes
from parsing.metadata import looks_word_boundary_corrupted
from parsing.task_blocks import NOTES_PATTERN
from tests.fixtures.known_cases import PDF_PATH


@pytest.fixture(scope="module")
def nodes():
    return build_nodes(PDF_PATH)


def test_notes_to_variant_recognized_as_section_boundary():
    assert NOTES_PATTERN.match("Notes to NSO 3.510 - 3.520")
    assert NOTES_PATTERN.match("Notes on PSO 2.220")


def test_3524_title_no_longer_swallows_footnote_section(nodes):
    title = nodes["3.524"].title
    assert "Notes" not in title
    assert "Page 57" not in title
    assert "Regional NSO Lead" not in title


@pytest.mark.parametrize("task_id", [
    "2.115", "2.223.2", "2.222.1", "2.222.2", "3.512", "3.524",
])
def test_known_corrupted_titles_recovered(nodes, task_id):
    title = nodes[task_id].title
    assert title, f"{task_id} has no title at all"


def test_2223_2_title_recovers_real_words(nodes):
    title = nodes["2.223.2"].title
    assert "Project Appraisal Report" in title
    assert "PAR" in title


def test_corruption_rate_stays_low(nodes):
    corrupted = [
        n.id for n in nodes.values() if looks_word_boundary_corrupted(n.title)
    ]
    assert len(corrupted) <= 2, f"unexpectedly high corruption: {corrupted}"

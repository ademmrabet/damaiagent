
import re

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from knowledge.typo_correct import correct_words

ID_SEARCH_PATTERN = re.compile(r"\d+(?:\.\d+){1,3}(?:\.[a-z])?")

SEARCHABLE_NODE_TYPES = {"process", "task", "child_task", "threshold_variant"}


def find_ids_in_query(query, nodes):
    """
    Every substring of `query` that looks like a DAM id AND actually
    exists in `nodes` - a candidate id that isn't real (typo, or just
    a number that happens to look like one) is silently not returned,
    rather than guessed at.
    """

    found = []

    for match in ID_SEARCH_PATTERN.finditer(query):
        candidate = match.group()
        if candidate in nodes and candidate not in found:
            found.append(candidate)

    return found


def _all_id_candidates(query):
    """
    Every id-shaped substring of `query`, valid or not - used to tell
    "the user typed something that looks like a DAM id, but it isn't
    one" apart from "the user typed a normal sentence with no id in
    it at all". Those two cases need different answers: the first
    should say the code doesn't exist, the second should fall through
    to text search.
    """
    found = []
    for match in ID_SEARCH_PATTERN.finditer(query):
        candidate = match.group()
        if candidate not in found:
            found.append(candidate)
    return found


def _shared_prefix_depth(a_id, b_id):
    depth = 0
    for x, y in zip(a_id.split("."), b_id.split(".")):
        if x != y:
            break
        depth += 1
    return depth


def suggest_ids_near(invalid_id, nodes, limit=3):
    """
    For an id-shaped string that doesn't exist, suggest real ids that
    share the longest possible dotted prefix (e.g. an invalid "3.999"
    suggests real tasks under chapter 3) - a simple, explainable
    nearest-neighbor rather than anything fuzzy or statistical. Empty
    if even the chapter number doesn't exist.
    """
    chapter = invalid_id.split(".")[0]
    candidates = [
        node for node in nodes.values()
        if node.node_type in SEARCHABLE_NODE_TYPES
        and node.title.strip()
        and node.id.split(".")[0] == chapter
    ]
    candidates.sort(key=lambda node: _shared_prefix_depth(invalid_id, node.id), reverse=True)
    return [{"id": node.id, "title": node.title} for node in candidates[:limit]]


def build_search_index(nodes):
    """
    Fits a TF-IDF vectorizer over every task/child_task/
    threshold_variant title (chapters/processes excluded - chapter
    titles are always blank, and "who approves X" questions are about
    activities, not whole process areas).

    Returns (vectorizer, matrix, searchable_ids) - searchable_ids[i]
    is the node id that matrix row i belongs to, since scikit-learn's
    matrix rows carry no id of their own.
    """

    searchable_ids = [
        node.id for node in nodes.values()
        if node.node_type in SEARCHABLE_NODE_TYPES and node.title.strip()
    ]
    titles = [nodes[node_id].title for node_id in searchable_ids]

    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
    matrix = vectorizer.fit_transform(titles)

    return vectorizer, matrix, searchable_ids


def _single_word_vocabulary(vectorizer):
    # vectorizer.vocabulary_ includes the fitted bigrams too (e.g.
    # "country strategy") alongside single words - only the single
    # words are meaningful things to typo-correct an individual query
    # word against.
    return {term for term in vectorizer.vocabulary_ if " " not in term}


def search_by_text(query, vectorizer, matrix, searchable_ids, top_k=5):
    """
    Ranks every searchable node by cosine similarity of its title to
    `query`. Returns [{"id", "score"}, ...], highest score first.
    Score is lexical overlap, not semantic similarity - a 0.0 means
    "shares no meaningful words with the query", not "definitely
    unrelated".

    The query is typo-corrected against the DAM's own title vocabulary
    before vectorizing (e.g. "qaurterly mision" -> "quarterly
    mission") - TF-IDF has zero inherent typo tolerance (a misspelled
    word is just an out-of-vocabulary token contributing nothing to
    the score), so a query with the right words but the wrong spelling
    would otherwise silently score low or match the wrong task instead
    of the intended one.
    """

    corrected_query = correct_words(query, _single_word_vocabulary(vectorizer))
    query_vector = vectorizer.transform([corrected_query])
    scores = cosine_similarity(query_vector, matrix)[0]

    ranked = np.argsort(scores)[::-1][:top_k]

    return [
        {"id": searchable_ids[i], "score": float(scores[i])}
        for i in ranked
        if scores[i] > 0
    ]


def resolve_query(query, nodes, vectorizer, matrix, searchable_ids, top_k=5):
    """
    The single entry point the agent should call. Three possible
    methods:

    - "id": the query contains a real DAM id - certain lookup.
    - "invalid_id": the query contains something id-SHAPED (digits and
      dots) that doesn't exist in `nodes`. Deliberately kept separate
      from "text_search" rather than falling through to it, because
      falling through would let leftover words in the query (e.g.
      "task", "who", "approves") match some UNRELATED real task by
      shared vocabulary and confidently answer about it - exactly the
      wrong behavior for a query about a specific, named, wrong code.
      Comes with `invalid_id` and `suggestions` instead of `matches`.
    - "text_search": no id-shaped substring at all - ranked TF-IDF
      guess over the whole query, as before.
    """

    id_matches = find_ids_in_query(query, nodes)

    if id_matches:
        return {
            "method": "id",
            "matches": [{"id": node_id, "score": 1.0} for node_id in id_matches],
        }

    id_candidates = _all_id_candidates(query)

    if id_candidates:
        invalid_id = id_candidates[0]
        suggestions = suggest_ids_near(invalid_id, nodes, limit=3)

        if not suggestions:
            stripped_query = ID_SEARCH_PATTERN.sub(" ", query)
            text_matches = search_by_text(stripped_query, vectorizer, matrix, searchable_ids, top_k=3)
            suggestions = [
                {"id": m["id"], "title": nodes[m["id"]].title}
                for m in text_matches if m["score"] > 0
            ]

        return {
            "method": "invalid_id",
            "matches": [],
            "invalid_id": invalid_id,
            "suggestions": suggestions,
        }

    return {
        "method": "text_search",
        "matches": search_by_text(query, vectorizer, matrix, searchable_ids, top_k),
    }

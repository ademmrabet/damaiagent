import re

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from knowledge.typo_correct import correct_words

ID_SEARCH_PATTERN = re.compile(r"\d+(?:\.\d+){1,3}(?:\.[a-z])?")

SEARCHABLE_NODE_TYPES = {"process", "task", "child_task", "threshold_variant"}


# ids written in the question that really exist in the matrix
def find_ids_in_query(query, nodes):

    found = []

    for match in ID_SEARCH_PATTERN.finditer(query):
        candidate = match.group()
        if candidate in nodes and candidate not in found:
            found.append(candidate)

    return found


# every id-shaped piece of text in the question, real or not
def _all_id_candidates(query):
    found = []
    for match in ID_SEARCH_PATTERN.finditer(query):
        candidate = match.group()
        if candidate not in found:
            found.append(candidate)
    return found


# how many leading id parts two ids share
def _shared_prefix_depth(a_id, b_id):
    depth = 0
    for x, y in zip(a_id.split("."), b_id.split(".")):
        if x != y:
            break
        depth += 1
    return depth


# suggest real ids that start like the invalid one
def suggest_ids_near(invalid_id, nodes, limit=3):
    chapter = invalid_id.split(".")[0]
    candidates = [
        node
        for node in nodes.values()
        if node.node_type in SEARCHABLE_NODE_TYPES
        and node.title.strip()
        and node.id.split(".")[0] == chapter
    ]
    candidates.sort(
        key=lambda node: _shared_prefix_depth(invalid_id, node.id), reverse=True
    )
    return [{"id": node.id, "title": node.title} for node in candidates[:limit]]


# fit the tf-idf index on the task titles
def build_search_index(nodes):

    searchable_ids = [
        node.id
        for node in nodes.values()
        if node.node_type in SEARCHABLE_NODE_TYPES and node.title.strip()
    ]
    titles = [nodes[node_id].title for node_id in searchable_ids]

    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
    matrix = vectorizer.fit_transform(titles)

    return vectorizer, matrix, searchable_ids


# single-word terms of the tf-idf vocabulary, used for typo fixing
def _single_word_vocabulary(vectorizer):
    return {term for term in vectorizer.vocabulary_ if " " not in term}


# best matching nodes for a text query, with scores
def search_by_text(query, vectorizer, matrix, searchable_ids, top_k=5):

    corrected_query = correct_words(query, _single_word_vocabulary(vectorizer))
    query_vector = vectorizer.transform([corrected_query])
    scores = cosine_similarity(query_vector, matrix)[0]

    ranked = np.argsort(scores)[::-1][:top_k]

    return [
        {"id": searchable_ids[i], "score": float(scores[i])}
        for i in ranked
        if scores[i] > 0
    ]


# single entry point: id lookup first, then text search
def resolve_query(query, nodes, vectorizer, matrix, searchable_ids, top_k=5):

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
            text_matches = search_by_text(
                stripped_query, vectorizer, matrix, searchable_ids, top_k=3
            )
            suggestions = [
                {"id": m["id"], "title": nodes[m["id"]].title}
                for m in text_matches
                if m["score"] > 0
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


TIGHT_CLUSTER_GAP = 3.0
COLUMN_MERGE_GAP = 14.0

SUBGROUP_TOLERANCE = 0.6
SUBGROUP_MIN_GAP = 1.5

FOOTNOTE_DIGIT_MAX_SIZE = 4.0


def _strip_trailing_footnote_digit(ordered_chars):
    """
    If the LAST character in a run is a small (shrunk) digit, treat it
    as a footnote reference and drop it - returns the chars list
    without it, or unchanged if there's nothing to strip.

    Checked against real counter-examples before using size alone:
    "Manager PGCL.1" / "Manager FIFC.4" / "Manager FITR.2" also end in
    a digit, but it's part of a formal department code (e.g. "FIFC.4"
    is one code, not "FIFC." plus a footnote), not a footnote
    reference - excluded by requiring the character BEFORE the digit
    not be a literal ".". Every confirmed real footnote-digit case
    (see module comment above) is preceded by a letter or a closing
    paren, never a period.

    Also found while checking this: the exact same code ("FIFC.4")
    renders its digit at NORMAL size on pages 33/48 but at the SHRUNK
    footnote size on page 49 - huge sample of one, and rebuilds on
    render inconsistency it can't decide alone, which is exactly why
    the period-exclusion matters as a second, independent check rather
    than relying on size in isolation.
    """

    non_space_indices = [
        i for i, c in enumerate(ordered_chars) if c["text"].strip()
    ]

    if not non_space_indices:
        return ordered_chars

    strip_from = None
    pos = len(non_space_indices) - 1

    while pos >= 0:
        idx = non_space_indices[pos]
        c = ordered_chars[idx]
        if c["text"].isdigit() and c["size"] < FOOTNOTE_DIGIT_MAX_SIZE:
            strip_from = idx
            pos -= 1
        else:
            break

    if strip_from is None:
        return ordered_chars

    remaining = non_space_indices[:pos + 1]

    if remaining and ordered_chars[remaining[-1]]["text"] == ".":
        return ordered_chars

    return ordered_chars[:strip_from]


def _cluster_by_x0(chars, gap):

    if not chars:
        return []

    ordered = sorted(chars, key=lambda c: c["x0"])
    clusters = [[ordered[0]]]

    for c in ordered[1:]:
        if c["x0"] - clusters[-1][-1]["x0"] <= gap:
            clusters[-1].append(c)
        else:
            clusters.append([c])

    return clusters


def _split_if_interleaved(cluster):
    """
    A tight x0-cluster can actually be TWO different columns' runs
    merged together (see module comment above). Detects this by
    checking whether the cluster's x0 values split cleanly into two
    or more sub-groups, each with multiple repeated members, separated
    by a real gap - not just a single stray outlier character. Returns
    a list of sub-clusters: either the original cluster unchanged (one
    element), or its genuine sub-runs split apart.
    """

    sub_groups = _cluster_by_x0(cluster, SUBGROUP_TOLERANCE)

    if len(sub_groups) < 2:
        return [cluster]

    gaps = [
        sub_groups[i + 1][0]["x0"] - sub_groups[i][-1]["x0"]
        for i in range(len(sub_groups) - 1)
    ]

    real_sub_runs = [g for g in sub_groups if len(g) >= 2]

    if max(gaps) < SUBGROUP_MIN_GAP or len(real_sub_runs) < 2:
        return [cluster]

    return sub_groups


def extract_column_headers(chars):
    """
    Returns [{"role": str, "x0": float}, ...] sorted left to right,
    from whichever rotated (upright=False) text is on the page - the
    DAM prints one header row per page's table, valid for every task
    on that page.
    """

    rotated = [c for c in chars if not c["upright"]]

    if not rotated:
        return []

    runs = []

    for cluster in _cluster_by_x0(rotated, TIGHT_CLUSTER_GAP):
        for sub_cluster in _split_if_interleaved(cluster):
            ordered_chars = sorted(sub_cluster, key=lambda c: -c["top"])
            ordered_chars = _strip_trailing_footnote_digit(ordered_chars)
            text = "".join(c["text"] for c in ordered_chars)
            x0_avg = sum(c["x0"] for c in sub_cluster) / len(sub_cluster)
            runs.append((x0_avg, text))

    runs.sort(key=lambda r: r[0])

    headers = []
    group_x0s = [runs[0][0]]
    group_text = runs[0][1]

    def _ends_with_balanced_parens(text):
        stripped = text.rstrip()
        return (
            stripped.endswith(")")
            and "(" in stripped
            and stripped.count("(") == stripped.count(")")
        )

    for x0, text in runs[1:]:

        already_closed = _ends_with_balanced_parens(group_text)

        if not already_closed and x0 - group_x0s[-1] <= COLUMN_MERGE_GAP:
            # NOT safe to unconditionally insert a space at this merge
            # boundary - tried that live on 2026-09-03 as a candidate
            # fix for the "Task Manager1 & Project Team Members" glued-
            # role-name bug (see docs/decisions.md) and it broke a
            # DIFFERENT, previously-correct case instead: "Sector
            # Manager (HQ-based / Region-based)" became "HQ- based"
            # because that merge boundary falls right after a hyphen,
            # which needs NO space. Confirmed by direct re-extraction
            # that the Task Manager1 case isn't even a wrapped-header-
            # merge issue in the first place (the missing space is
            # inside a single run, between "Manager" and a shrunk "1"
            # that looks like an unstripped mid-string footnote digit -
            # a real, separate, narrower issue, left as a known
            # limitation rather than chasing a risky general fix here).
            group_text += text
            group_x0s.append(x0)
        else:
            role = " ".join(group_text.split())
            if role:
                headers.append({
                    "role": role,
                    "x0": sum(group_x0s) / len(group_x0s)
                })
            group_text = text
            group_x0s = [x0]

    role = " ".join(group_text.split())
    if role:
        headers.append({
            "role": role,
            "x0": sum(group_x0s) / len(group_x0s)
        })

    return headers


def nearest_role(headers, action_x0, max_distance=20.0):
    """
    The header whose x0 is closest to `action_x0`. Returns None if
    there are no headers or the closest one is implausibly far away
    (bad match is worse than no match - a null role is honest, a
    wrong one is a silent bug).
    """

    if not headers:
        return None

    closest = min(headers, key=lambda h: abs(h["x0"] - action_x0))

    if abs(closest["x0"] - action_x0) > max_distance:
        return None

    return closest["role"]

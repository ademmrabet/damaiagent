TIGHT_CLUSTER_GAP = 3.0
COLUMN_MERGE_GAP = 14.0

SUBGROUP_TOLERANCE = 0.6
SUBGROUP_MIN_GAP = 1.5

FOOTNOTE_DIGIT_MAX_SIZE = 4.0


# drop a footnote digit stuck to the end of a role name
def _strip_trailing_footnote_digit(ordered_chars):

    non_space_indices = [i for i, c in enumerate(ordered_chars) if c["text"].strip()]

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

    remaining = non_space_indices[: pos + 1]

    if remaining and ordered_chars[remaining[-1]]["text"] == ".":
        return ordered_chars

    return ordered_chars[:strip_from]


# group characters into columns by their left position
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


# split a column group that is really two columns mixed together
def _split_if_interleaved(cluster):

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


# read the rotated role names printed at the top of the columns
def extract_column_headers(chars):

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
            group_text += text
            group_x0s.append(x0)
        else:
            role = " ".join(group_text.split())
            if role:
                headers.append({"role": role, "x0": sum(group_x0s) / len(group_x0s)})
            group_text = text
            group_x0s = [x0]

    role = " ".join(group_text.split())
    if role:
        headers.append({"role": role, "x0": sum(group_x0s) / len(group_x0s)})

    return headers


# role header closest to the action's horizontal position
def nearest_role(headers, action_x0, max_distance=20.0):

    if not headers:
        return None

    closest = min(headers, key=lambda h: abs(h["x0"] - action_x0))

    if abs(closest["x0"] - action_x0) > max_distance:
        return None

    return closest["role"]

def classify_relative_position(base_char, candidate_char):

    base_center = (base_char["top"] + base_char["bottom"]) / 2
    candidate_center = (candidate_char["top"] + candidate_char["bottom"]) / 2

    delta = candidate_center - base_center

    if delta > 1:
        return "subscript"

    elif delta < -1:
        return "superscript"

    else:
        return "baseline"


def extract_action_metadata(base_char, chars, x_tolerance=15):

    result = {
        "action": base_char["text"],
        "authority_modifier": None,
        "note_reference": None
    }

    base_x = base_char["x0"]

    superscripts = []
    subscripts = []

    for c in chars:

        if c == base_char:
            continue

        if not c["text"].isdigit():
            continue

        distance = c["x0"] - base_x
        vertical_distance = abs(c["top"] - base_char["top"])

        if distance < 0:
            continue

        if distance > x_tolerance:
            continue

        if vertical_distance > 10:
            continue

        relation = classify_relative_position(base_char, c)

        if relation == "subscript":
            subscripts.append(c)

        elif relation == "superscript":
            superscripts.append(c)

    # LEFT → RIGHT
    subscripts.sort(key=lambda x: x["x0"])
    superscripts.sort(key=lambda x: x["x0"])

    if subscripts:
        result["authority_modifier"] = "".join(
            s["text"] for s in subscripts
        )

    if superscripts:
        result["note_reference"] = "".join(
            s["text"] for s in superscripts
        )

    return result
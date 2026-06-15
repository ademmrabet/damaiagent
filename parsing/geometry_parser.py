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


def extract_action_metadata(base_char, chars, x_tolerance=40):

    result = {
        "action": base_char["text"],
        "authority_modifier": None,
        "note_references": []
    }

    base_x = base_char["x0"]

    superscripts = []
    subscripts = []

    for c in chars:

        if c == base_char:
            continue

        if not (c["text"].isdigit() or c["text"] == "/"):
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

        if relation == "superscript":
            print(
                "SUPER:",
                c["text"],
                "x=", round(c["x0"],1),
                "top=", round(c["top"],1)
            )
            superscripts.append(c)
    # LEFT → RIGHT
    subscripts.sort(key=lambda x: x["x0"])
    superscripts.sort(key=lambda x: x["x0"])

    filtered_superscripts = []
    if superscripts:
        filtered_superscripts.append(superscripts[0])

        for current in superscripts[1:]:
            previous = filtered_superscripts[-1]
            gap = current["x0"] - previous["x0"]

            if gap <= 6:
                filtered_superscripts.append(current)
            else:
                break
        superscripts = filtered_superscripts

    if subscripts:
        result["authority_modifier"] = "".join(
            s["text"] for s in subscripts
        )

    if superscripts:

        raw_note = "".join(
            s["text"] for s in superscripts
        )

        result["note_references"] = [
            n.strip()
            for n in raw_note.split("/")
            if n.strip()
        ]

        
    return result
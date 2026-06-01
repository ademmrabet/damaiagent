import re

ACTION_PATTERN = re.compile(
    r"^(I|C|R\d*|A\d*)$"
)

def detect_action_columns(words):
    action_words = []

    for w in words:
        if w["top"] < 200: # ignore upper legends / headers
            continue
        if ACTION_PATTERN.match(w["text"]):
            action_words.append({
                "action": w["text"],
                "x": round(w["x0"], 0),
                "top": round(w["top"], 1),
            })
    return action_words

def cluster_columns(action_words, tolerance=15):
    columns = []

    for action in action_words:
        x = action["x"]
        matched = False
        for column in columns:
            if abs(column["center"] - x) <= tolerance:
                column["positions"].append(x)
                column["center"] = (
                    sum(column["positions"]) / len(column["positions"])
                )

                matched = True
                break
        
        if not matched:
            columns.append({
                "center": x,
                "positions": [x]
            })
    return columns    

def extract_row_actions(words, row_top, tolerance=5):
    row_actions = []

    for w in words:

        # same visual row
        if abs(w["top"] - row_top) > tolerance:
            continue

        # ignore upper-page junk
        if w["top"] < 200:
            continue

        text = w["text"]

        # valid action patterns
        if ACTION_PATTERN.match(text):

            row_actions.append({
                "action": text,
                "x": round(w["x0"], 0),
                "top": round(w["top"], 1),
            })

    return row_actions

import re
from modeling.authority_rules import interpret_action
from parsing.authority_mapper import get_authority_meaning

ACTION_PATTERN = re.compile(r"\(\s*i\s*\)|\b[ICRA]\d*\b")

def parse_task_row(line):

    parts = line.split()
    task_id = parts[0]

    # remove the task_id from the parts list
    content = " ".join(parts[1:])
    # Extract actions
    raw_actions = ACTION_PATTERN.findall(content)
    actions = [parse_action(a) for a in raw_actions]
    # Remove actions from descriptions
    description = ACTION_PATTERN.sub("", content)
    #clean extra spaces
    description = " ".join(description.split())

    return{
        "task_id": task_id,
        "description": description,
        "actions": actions
    }

def parse_action(action):
    action = action.strip()

    # handle informed
    if action.replace(" ", "") == "(i)":
        return {
            "code": "i",
            "modifier": None,
            "meaning": interpret_action("i")
        }
    
    code = action[0]
    modifier = None

    if len(action) > 1:
        digits = action[1:]

        if digits.isdigit():
            modifier = int(digits)

    return {
        "code": code,
        "authority_level": modifier,
        "meaning": get_authority_meaning(code, modifier)
    }
import json

with open("../Data/authority_code.json", "r") as f:
    AUTHORITY_CODES = json.load(f)

def get_authority_meaning(code, level=None):

    if code == "i":
        return AUTHORITY_CODES["i"]
    if level is None:
        return None
    
    key =f"{code}{level}"
    return AUTHORITY_CODES.get(key)
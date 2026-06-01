# Big Brain DAM AI Agent -> Here we define the interior ministry or The RH in our case

def interpret_action(code, modifier=None):
    # INFORMED 
    if code == "i":
        return "To Be Informed"
    
    # INITIATE
    if code == "I":
        return "Initiate / Originate"
    
    # CHECK
    if code == "C":
        return "Check and Verify"
    
    # REVIEW
    if code == "R":
        return "Review and Recommend"
    
    # APPROVE
    if code == "A":

        if modifier == 1:
            return "Endorse"

        return "Approve"

    return "Unknown"
    
    

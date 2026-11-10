#helper functions used to convert odds data into a format suitable for training machine learning models

#convert decimal odds values into implied probabilities
def odds_to_proba(odds):
    return 1 / odds


def normalise_result_proba(h_odds, d_odds, a_odds):
    h_proba = odds_to_proba(h_odds)
    d_proba = odds_to_proba(d_odds)
    a_proba = odds_to_proba(a_odds)

    total = h_proba + d_proba + a_proba

    return h_proba / total, d_proba / total, a_proba / total


def normalise_ou_proba(o_odds, u_odds):

    o_proba = odds_to_proba(o_odds)
    u_proba = odds_to_proba(u_odds)

    total = o_proba + u_proba

    return o_proba / total, u_proba / total
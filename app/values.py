"""Company core values that a kudos can be tagged with.

These map directly to the recognition scenarios in the program brief:
great teammate, handling difficult clients, and crisis help — plus a few more.
"""

# Colors are drawn from the OpenTeams brand palette (navy / blue / coral /
# gold) plus two complementary hues so the six values stay distinguishable.
CORE_VALUES = [
    {"key": "great_teammate", "label": "Great Teammate", "emoji": "🤝",
     "color": "#4D75FE", "desc": "A great friend and collaborator"},
    {"key": "client_hero", "label": "Client Hero", "emoji": "🛡️",
     "color": "#1F8A8A", "desc": "Expertly handled a difficult client"},
    {"key": "crisis_crusher", "label": "Crisis Crusher", "emoji": "🚒",
     "color": "#FF8A69", "desc": "Critical help during a crisis"},
    {"key": "above_beyond", "label": "Above & Beyond", "emoji": "🚀",
     "color": "#FAA944", "desc": "Went above and beyond the call of duty"},
    {"key": "innovator", "label": "Innovator", "emoji": "💡",
     "color": "#2E9E6B", "desc": "Brought a bright idea to life"},
    {"key": "mentor", "label": "Mentor", "emoji": "🌱",
     "color": "#7C5CFF", "desc": "Lifted others up through mentorship"},
]

VALUES_BY_KEY = {v["key"]: v for v in CORE_VALUES}


def value_or_default(key: str) -> dict:
    return VALUES_BY_KEY.get(key, CORE_VALUES[0])

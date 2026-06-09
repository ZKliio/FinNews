WIRE_ACCOUNTS = [
    "DeItaone",
    "FirstSquawk",
    "LiveSquawk",
    "FinancialJuice",
]

ANALYSIS_ACCOUNTS = [
    "KobeissiLetter",
    "Serenity_Res",
    "TheValuist",
    "jukan_05",
    "MacroAlf",
    "unusual_whales",
    "zaborhedge",
]

MEDIA_ACCOUNTS = [
    "business",
    "ReutersBiz",
    "financialtimes",
    "WSJ",
    "Markets",
]

ALL_ACCOUNTS = WIRE_ACCOUNTS + ANALYSIS_ACCOUNTS + MEDIA_ACCOUNTS

ACCOUNT_RELIABILITY = {
    "DeItaone": {"tier": "wire", "credibility": 0.95, "speed": "fastest"},
    "FirstSquawk": {"tier": "wire", "credibility": 0.95, "speed": "fastest"},
    "LiveSquawk": {"tier": "wire", "credibility": 0.90, "speed": "fast"},
    "FinancialJuice": {"tier": "wire", "credibility": 0.90, "speed": "fast"},
    "KobeissiLetter": {"tier": "analysis", "credibility": 0.85, "speed": "medium"},
    "Serenity_Res": {"tier": "analysis", "credibility": 0.85, "speed": "medium"},
    "TheValuist": {"tier": "analysis", "credibility": 0.80, "speed": "medium"},
    "jukan_05": {"tier": "analysis", "credibility": 0.80, "speed": "medium"},
    "MacroAlf": {"tier": "analysis", "credibility": 0.85, "speed": "medium"},
    "unusual_whales": {"tier": "analysis", "credibility": 0.75, "speed": "fast"},
    "zaborhedge": {"tier": "analysis", "credibility": 0.70, "speed": "fast"},
    "business": {"tier": "media", "credibility": 0.90, "speed": "slow"},
    "ReutersBiz": {"tier": "media", "credibility": 0.95, "speed": "slow"},
    "financialtimes": {"tier": "media", "credibility": 0.90, "speed": "slow"},
    "WSJ": {"tier": "media", "credibility": 0.90, "speed": "slow"},
    "Markets": {"tier": "media", "credibility": 0.85, "speed": "slow"},
}

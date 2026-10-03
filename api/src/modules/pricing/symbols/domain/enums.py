from papilio.types.enums import FaStrEnum


class SymbolCode(FaStrEnum):
    GOLD18_GRAM = ("gold18_gram", "طلای ۱۸ عیار، هر گرم")
    GOLD18_MAZANE = ("gold18_mazane", "مظنه طلای ۱۸ عیار")
    XAU_OUNCE = ("xau_ounce", "انس جهانی طلا")
    SILVER_GRAM = ("silver_gram", "هر گرم نقره ۹۹۹")
    XAG_OUNCE = ("xag_ounce", "انس جهانی نقره")
    USD_RIAL = ("usd_rial", "دلار به ریال")
    USDT_RIAL = ("usdt_rial", "تتر به ریال")


class CurrencyType(FaStrEnum):
    RIAL = ("rial", "ریال")
    USD = ("usd", "دلار")

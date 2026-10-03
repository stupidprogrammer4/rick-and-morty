from papilio.types.enums import FaStrEnum


class AssetCode(FaStrEnum):
    GOLD18 = ("gold18", "طلای ۱۸ عیار")
    SILVER999 = ("silver999", "نقره ۹۹۹")
    USD = ("usd", "دلار")
    USDT = ("usdt", "تتر")


class AggregationType(FaStrEnum):
    MEDIAN = ("median", "میانه")
    MEAN = ("mean", "میانگین")
    MIN = ("min", "کمترین")
    MAX = ("max", "بیشترین")
    FIRST_QUARTILE = ("first_quartile", "چارک اول")
    THIRD_QUARTILE = ("third_quartile", "چارک سوم")

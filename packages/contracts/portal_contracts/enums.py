from enum import StrEnum


class BotRole(StrEnum):
    RICK = "rick"
    MORTY = "morty"


class Actor(StrEnum):
    RICK = "rick"
    MORTY = "morty"
    TEAM = "team"


class Intent(StrEnum):
    CHAT = "chat"
    NEWS = "news"
    SUMMARY = "summary"
    PRICES = "prices"
    CHARTS = "charts"
    OCCASIONS = "occasions"


class Category(StrEnum):
    NEWS = "news"
    TECH = "tech"
    MUSIC = "music"
    MARKET = "market"
    CHARTS = "charts"
    NOTICE = "notice"
    OCCASIONS = "occasions"

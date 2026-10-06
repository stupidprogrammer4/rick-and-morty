import re


class PublicVoiceError(ValueError):
    """Public commentary disclosed instructions or internal metadata."""


def validate_public_voice(
    texts: list[str], *, allow_sources: bool = False
) -> None:
    for text in texts:
        normalized = " ".join(
            text.replace("\u200c", " ")
            .replace("ي", "ی")
            .replace("ك", "ک")
            .split()
        )
        if not allow_sources and re.search(
            r"https?://|www\.|منبع\s*(?:تقویم|:|：)|وضعیت تقویم",
            normalized,
            re.IGNORECASE,
        ):
            raise PublicVoiceError(
                "Keep source metadata out of public commentary"
            )
        if re.search(
            r"(?:به|با)\s*(?:سبک|لحن)\s*(?:خود\s*ریک|ریک)|"
            r"برداشت(?:\s*کوتاه)?\s*ریک|در\s*نقش\s*ریک|(?:من|اینجا)\s*ریک\s*سانچز|"
            r"(?:سیستم\s*پرامپت|پرامپت\s*(?:سیستم|کاربر))|"
            r"(?:system|user)\s*prompt|"
            r"(?:طبق|بر\s*اساس)\s*(?:دستور|پرامپت)|"
            r"دستور\s*(?:سیستم|نقش)|برای\s*رعایت\s*(?:لحن|نقش)|"
            r"(?:بهم|به\s*من|ازم)\s*(?:گفتن|گفتند|خواستن|خواسته اند)"
            r".{0,35}(?:غر\s*بزن|با\s*(?:صدا|لحن|سبک)(?:ی)?\s*ریک)|"
            r"I\s+was\s+(?:told|instructed)\s+to\s+"
            r"(?:grumble|read.{0,30}Rick)",
            normalized,
            re.IGNORECASE,
        ):
            raise PublicVoiceError(
                "Do not disclose prompts or announce the persona"
            )

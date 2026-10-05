import re
import unicodedata
from collections.abc import Sequence
from difflib import SequenceMatcher

from portal_contracts.media import MediaPolicy
from src.modules.media.sources.domain.dtos import DownloadItem
from src.modules.media.sources.domain.music import MusicCandidate, MusicMatch


class MusicMatching:
    def __init__(self, policy: MediaPolicy):
        self.policy = policy

    def words(self, value: str) -> str:
        value = unicodedata.normalize("NFKC", value).casefold()
        return " ".join(re.findall(r"[^\W_]+", value))

    def score(self, item: DownloadItem, candidate: MusicCandidate) -> float:
        if not item.performer or not candidate.duration or not item.duration:
            return 0
        if abs(candidate.duration - item.duration) > max(
            3, item.duration * self.policy.music_duration_tolerance
        ):
            return 0
        requested = self.words(item.title)
        title = self.words(candidate.title)
        for version in (
            "live",
            "remix",
            "cover",
            "karaoke",
            "instrumental",
            "slowed",
            "sped up",
            "acoustic",
            "remaster",
        ):
            marker = (
                r"\bre ?master(?:ed)?\b"
                if version == "remaster"
                else r"\b" + re.escape(version) + r"\b"
            )
            if bool(re.search(marker, requested)) != bool(
                re.search(marker, title)
            ):
                return 0
        artist = self.words(item.performer.split(",", 1)[0])
        attribution = self.words(
            candidate.title + " " + (candidate.performer or "")
        )
        artist_tokens = set(artist.split())
        if not artist_tokens or not artist_tokens.issubset(
            attribution.split()
        ):
            return 0
        if item.isrc and candidate.isrc:
            return (
                1 if item.isrc.casefold() == candidate.isrc.casefold() else 0
            )
        licensed = re.sub(
            r"[\[(][^\])]*\bcc[- ]by\b[^\])]*[\])]",
            "",
            candidate.title,
            flags=re.IGNORECASE,
        )
        cleaned = " ".join(
            word
            for word in self.words(licensed).split()
            if word
            not in {
                "official",
                "audio",
                "video",
                "lyrics",
                "hd",
                "hq",
                "mastered",
            }
        )
        if cleaned.startswith(artist + " "):
            cleaned = cleaned[len(artist) + 1 :]
        elif cleaned.endswith(" " + artist):
            cleaned = cleaned[: -len(artist) - 1]
        return SequenceMatcher(None, requested, cleaned).ratio()

    def rank(
        self, item: DownloadItem, candidates: Sequence[MusicCandidate]
    ) -> list[MusicMatch]:
        ranked = [
            MusicMatch(candidate=candidate, score=self.score(item, candidate))
            for candidate in candidates
        ]
        return sorted(
            (
                match
                for match in ranked
                if match.score >= self.policy.music_match_threshold
            ),
            key=lambda match: match.score,
            reverse=True,
        )

import sys

# Commit-pinned framework sources require a separate code review.
for line in sys.stdin:
    text = line.strip()
    if "==" in text and not text.lower().startswith(
        (
            "portal-api==",
            "portal-bots==",
            "portal-contracts==",
            "papilio==",
            "papilio-tasks==",
        )
    ):
        print(text)

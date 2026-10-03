import argparse
import json
import logging
from pathlib import Path

import httpx
from dotenv import dotenv_values


class TelegramChannelDiscovery:
    def __init__(self, client: httpx.Client, tokens: dict[str, str]):
        self.client = client
        self.tokens = tokens

    def call(self, role: str, method: str, **data):
        response = self.client.post(
            f"https://api.telegram.org/bot{self.tokens[role]}/{method}",
            json=data,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError(f"Telegram {method} failed")
        return payload["result"]

    def discover(self, known_channel: int | str | None = None):
        identities = {role: self.call(role, "getMe") for role in self.tokens}
        if len({item["id"] for item in identities.values()}) != 2:
            raise RuntimeError("Independent bot identities are required")
        candidates = {known_channel} if known_channel else set()
        for role in self.tokens:
            webhook = self.call(role, "getWebhookInfo")
            if webhook.get("url"):
                print(f"{role}: existing webhook retained")
                continue
            # No offset: inspection does not acknowledge pending updates.
            updates = self.call(role, "getUpdates", timeout=0, limit=100)
            for update in updates:
                for key in (
                    "my_chat_member",
                    "channel_post",
                    "edited_channel_post",
                    "message",
                ):
                    event = update.get(key, {})
                    chat = event.get("chat", {})
                    if chat.get("type") == "channel":
                        candidates.add(chat["id"])
                    forwarded = event.get("forward_origin", {})
                    origin = forwarded.get("chat", {})
                    if forwarded.get("type") == "channel":
                        candidates.add(origin["id"])
        verified = []
        for channel_id in candidates:
            try:
                members = {
                    role: self.call(
                        role,
                        "getChatMember",
                        chat_id=channel_id,
                        user_id=identity["id"],
                    )
                    for role, identity in identities.items()
                }
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in {400, 403}:
                    continue
                raise
            if not all(
                member["status"] == "creator"
                or (
                    member["status"] == "administrator"
                    and member.get("can_post_messages", False)
                )
                for member in members.values()
            ):
                continue
            chat = self.call("rick", "getChat", chat_id=channel_id)
            verified.append(chat)
        if len(verified) != 1:
            raise RuntimeError(
                "One shared channel with posting permissions was not found. "
                "Bot API cannot enumerate all memberships."
            )
        return verified[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, default=Path(".env.runtime"))
    parser.add_argument("--write-policy", action="store_true")
    channel = parser.add_mutually_exclusive_group()
    channel.add_argument("--channel-id", type=int)
    channel.add_argument("--channel", help="Public @username or numeric ID")
    args = parser.parse_args()
    values = dotenv_values(args.env_file)
    tokens = {
        "rick": values.get("PORTAL_RICK_BOT_TOKEN")
        or values.get("RICK_TG_BOT")
        or "",
        "morty": values.get("PORTAL_MORTY_BOT_TOKEN")
        or values.get("MORTY_TG_BOT")
        or "",
    }
    if not all(tokens.values()):
        raise SystemExit("Both private bot tokens are required")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        with httpx.Client(timeout=10, trust_env=False) as client:
            chat = TelegramChannelDiscovery(client, tokens).discover(
                args.channel_id or args.channel
            )
            print("Verified common posting channel:", chat["id"])
            if args.write_policy:
                owner = min(
                    int(item)
                    for item in str(values["PORTAL_ADMIN_USER_IDS"]).split(",")
                )
                headers = {
                    "Authorization": "Bearer "
                    + str(values["PORTAL_SERVICE_KEY"]),
                    "X-Portal-Owner": str(owner),
                }
                url = (
                    "http://127.0.0.1:18010/internal/configuration/values/"
                    "portal.policy/global"
                )
                current = client.get(url, headers=headers)
                current.raise_for_status()
                record = current.json()["data"]
                policy = json.loads(record["value"])
                policy["channel_id"] = chat["id"]
                saved = client.put(
                    url,
                    headers=headers,
                    json={
                        "revision": record["revision"],
                        "value": json.dumps(policy),
                    },
                )
                saved.raise_for_status()
                print("Channel stored in the database policy")
    except (httpx.HTTPError, OSError) as exc:
        raise SystemExit(
            f"Channel discovery blocked: {type(exc).__name__}"
        ) from None
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from None


if __name__ == "__main__":
    main()

import secrets
from pathlib import Path
from urllib.parse import quote

from dotenv import dotenv_values


def main() -> None:
    source = dotenv_values(".env")
    proxy = Path.home() / "w/Personal/papilio-proxy/.env"
    server = dotenv_values(proxy) if proxy.exists() else {}
    destination = Path(".env.runtime")
    if destination.exists():
        raise SystemExit(".env.runtime already exists; retained unchanged.")
    password = secrets.token_urlsafe(32)
    values = {
        "RICK_TG_BOT": source.get("RICK_TG_BOT", ""),
        "MORTY_TG_BOT": source.get("MORTY_TG_BOT", ""),
        "OPENROUTER_API_KEY": source.get("OPENROUTER_API_KEY", ""),
        "PORTAL_SERVICE_KEY": secrets.token_urlsafe(40),
        "PORTAL_RICK_WEBHOOK_SECRET": secrets.token_urlsafe(40),
        "PORTAL_MORTY_WEBHOOK_SECRET": secrets.token_urlsafe(40),
        "PORTAL_ADMIN_USER_IDS": server.get("ADMIN_TELEGRAM_IDS", ""),
        "PORTAL_WEBHOOK_BASE_URL": "https://bot.amupouya.org",
        "PORTAL_DRY_RUN": "true",
        "MYSQL_PASSWORD": password,
        "MYSQL_ROOT_PASSWORD": secrets.token_urlsafe(32),
        "PORTAL_DATABASE_URL": f"mysql+aiomysql://portal:{quote(password)}@mysql:3306/portal",
        "PORTAL_REDIS_URL": "redis://redis:6379/0",
        "PORTAL_API_URL": "http://api:8000",
        "PAPILIO_CONFIG": "config.yml",
    }
    with destination.open("x", encoding="utf-8") as handle:
        destination.chmod(0o600)
        handle.write(
            "\n".join(f"{key}={value or ''}" for key, value in values.items())
            + "\n"
        )
    config = Path("config.yml")
    if not config.exists():
        config.write_text(Path("config.yml.sample").read_text())
    print(
        "Created private .env.runtime and config.yml; original .env retained."
    )


if __name__ == "__main__":
    main()

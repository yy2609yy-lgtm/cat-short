"""One-time YouTube OAuth (live mode).

Run on a machine with a browser:

    python -m app.tools.oauth_youtube

Requires YOUTUBE_CLIENT_SECRETS_FILE. Writes YOUTUBE_TOKEN_FILE.
"""

from app.config import settings


def main() -> None:
    from google_auth_oauthlib.flow import InstalledAppFlow

    settings.ensure_dirs()
    if not settings.youtube_client_secrets_file.exists():
        raise SystemExit(
            f"Missing {settings.youtube_client_secrets_file}. "
            "Create an OAuth Desktop client and enable YouTube Data API v3."
        )
    flow = InstalledAppFlow.from_client_secrets_file(
        str(settings.youtube_client_secrets_file),
        scopes=[
            "https://www.googleapis.com/auth/youtube.upload",
            "https://www.googleapis.com/auth/youtube",
        ],
    )
    creds = flow.run_local_server(port=0)
    settings.youtube_token_file.parent.mkdir(parents=True, exist_ok=True)
    settings.youtube_token_file.write_text(creds.to_json(), encoding="utf-8")
    print(f"Wrote YouTube token → {settings.youtube_token_file}")
    print("Set YOUTUBE_MODE=live and restart. Uploads stay private until you click 发布.")


if __name__ == "__main__":
    main()

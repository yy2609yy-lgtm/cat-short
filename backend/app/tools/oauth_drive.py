"""One-time Google Drive OAuth (live mode).

Run on a machine with a browser:

    python -m app.tools.oauth_drive

Requires GOOGLE_CLIENT_SECRETS_FILE (OAuth desktop client JSON).
Writes GOOGLE_TOKEN_FILE for the worker/scheduler to use.
"""

from app.config import settings


def main() -> None:
    from google_auth_oauthlib.flow import InstalledAppFlow

    settings.ensure_dirs()
    if not settings.google_client_secrets_file.exists():
        raise SystemExit(
            f"Missing {settings.google_client_secrets_file}. "
            "Create an OAuth Desktop client in Google Cloud Console and save the JSON there."
        )
    flow = InstalledAppFlow.from_client_secrets_file(
        str(settings.google_client_secrets_file),
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    )
    creds = flow.run_local_server(port=0)
    settings.google_token_file.parent.mkdir(parents=True, exist_ok=True)
    settings.google_token_file.write_text(creds.to_json(), encoding="utf-8")
    print(f"Wrote Drive token → {settings.google_token_file}")
    print("Set DRIVE_MODE=live and DRIVE_FOLDER_ID=<folder id>, then restart.")


if __name__ == "__main__":
    main()

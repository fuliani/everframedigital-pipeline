"""Authorize the Etsy app without creating or modifying listings."""

import os
from pathlib import Path

from dotenv import load_dotenv

from scripts.etsy_publish.auth import EtsyAuth


REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    load_dotenv(REPO_ROOT / ".env", override=True)
    auth = EtsyAuth(
        os.environ["ETSY_API_KEY"],
        os.environ["ETSY_API_SECRET"],
        os.environ.get("ETSY_REDIRECT_URI", "http://localhost:3003/oauth/redirect"),
        str(REPO_ROOT / "etsy_token.json"),
    )
    if auth.is_authenticated():
        print("Already authenticated.", flush=True)
        return
    if not auth.start_oauth_flow(timeout=300):
        raise SystemExit("OAuth authorization failed or timed out.")
    print("OAuth authorization completed and token saved.", flush=True)


if __name__ == "__main__":
    main()

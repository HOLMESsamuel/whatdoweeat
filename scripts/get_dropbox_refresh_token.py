"""One-time helper to generate a Dropbox refresh token for whatdoweeat.

This is a manual step you run locally. Once you have the refresh token
you can put it in `prod/.env` and forget about it — Dropbox refresh
tokens don't expire unless you revoke them.

Setup:

  1. Go to https://www.dropbox.com/developers/apps and click "Create app".
     - API: "Scoped access"
     - Access type: "Full Dropbox" (so it can read your existing
       Recettes folder; "App folder" would force you to move it).
     - Name: anything, e.g. "whatdoweeat-recipes".
  2. On the app's settings page, under "Permissions", check:
       - files.metadata.read
       - files.content.read
     Click "Submit" at the bottom.
  3. Note the App key and App secret on the Settings tab.
  4. Run this script with those values:

       python scripts/get_dropbox_refresh_token.py

     It will print an authorization URL. Open it in a browser, click
     "Allow", copy the code Dropbox gives you, and paste it back here.
     The script then prints your refresh token.

  5. Put the values in prod/.env (see prod/README.md).

Refresh tokens are long-lived and survive token expiry / app restarts.
The Dropbox SDK transparently mints fresh access tokens from them.
"""

from __future__ import annotations

import getpass
import sys

try:
    from dropbox import DropboxOAuth2FlowNoRedirect
except ImportError:
    sys.exit(
        "The `dropbox` package is required.\n"
        "Install it with: pip install dropbox==12.0.2"
    )


def main() -> None:
    print("Dropbox refresh-token helper for whatdoweeat\n")
    app_key = input("App key:    ").strip()
    app_secret = getpass.getpass("App secret: ").strip()
    if not app_key or not app_secret:
        sys.exit("App key and secret are both required.")

    flow = DropboxOAuth2FlowNoRedirect(
        consumer_key=app_key,
        consumer_secret=app_secret,
        token_access_type="offline",  # gives us a refresh token
    )

    auth_url = flow.start()
    print("\n1. Open this URL in your browser:")
    print(f"\n   {auth_url}\n")
    print("2. Click 'Allow' (you may need to log in to Dropbox first).")
    print("3. Copy the authorization code Dropbox shows you.\n")

    auth_code = input("Authorization code: ").strip()
    if not auth_code:
        sys.exit("No authorization code provided.")

    try:
        result = flow.finish(auth_code)
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"Failed to exchange code for tokens: {exc}")

    print("\nDone. Add the following to prod/.env:\n")
    print(f"DROPBOX_APP_KEY={app_key}")
    print(f"DROPBOX_APP_SECRET={app_secret}")
    print(f"DROPBOX_REFRESH_TOKEN={result.refresh_token}")
    print(
        "DROPBOX_RECIPES_PATH=/ideaverse/Recettes/recette-templated"
        "  # adjust if your path is different"
    )
    print()
    print("Treat the refresh token as a secret — anyone with it can read")
    print("all your Dropbox files. You can revoke it at any time from")
    print("https://www.dropbox.com/account/connected_apps.")


if __name__ == "__main__":
    main()

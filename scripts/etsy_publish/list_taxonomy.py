"""
One-time setup helper: find the correct Etsy taxonomy_id for digital prints.

Etsy's seller-taxonomy endpoint is public (no shop auth needed), so this runs
before you've even connected your shop. Usage:

    python -m scripts.etsy_publish.list_taxonomy "digital"

Prints matching category nodes with their ids so you can put the right one
in .env as ETSY_TAXONOMY_ID. Do not trust a hardcoded guess -- Etsy's
taxonomy ids are not documented as stable across API versions, so confirm
here before your first listing.
"""

import sys

import requests

BASE_URL = "https://openapi.etsy.com/v3/application/seller-taxonomy/nodes"


def main():
    query = sys.argv[1].lower() if len(sys.argv) > 1 else "print"
    api_key = _get_api_key()
    resp = requests.get(BASE_URL, headers={"x-api-key": api_key})
    resp.raise_for_status()
    nodes = resp.json().get("results", [])

    def walk(nodes, path=""):
        for n in nodes:
            full_path = f"{path} > {n['name']}" if path else n["name"]
            if query in full_path.lower():
                print(f"{n['id']:>10}  {full_path}")
            walk(n.get("children", []), full_path)

    walk(nodes)


def _get_api_key() -> str:
    import os

    from dotenv import load_dotenv

    load_dotenv()
    key = os.environ.get("ETSY_API_KEY")
    if not key:
        print("Set ETSY_API_KEY in .env first (this only needs the API key, "
              "not full OAuth).", file=sys.stderr)
        sys.exit(1)
    return key


if __name__ == "__main__":
    main()

"""Check LinkedIn token setup without printing secrets."""
import hashlib

import requests

from config import settings


LINKEDIN_VERSION = "202508"


def _get(url: str, *, restli: bool = False, versioned: bool = False) -> tuple[int | None, dict | str]:
    headers = {"Authorization": f"Bearer {settings.LINKEDIN_ACCESS_TOKEN}"}
    if restli:
        headers["X-Restli-Protocol-Version"] = "2.0.0"
    if versioned:
        headers["LinkedIn-Version"] = LINKEDIN_VERSION

    try:
        resp = requests.get(
            url,
            headers=headers,
            timeout=20,
        )
    except requests.RequestException as exc:
        return None, str(exc)

    try:
        payload = resp.json()
    except ValueError:
        payload = resp.text[:500]
    return resp.status_code, payload


def _print_profile_result(label: str, status: int | None, payload: dict | str) -> str | None:
    print(f"[{label}] status={status}")
    if isinstance(payload, dict):
        person_id = payload.get("id") or payload.get("sub")
        if person_id:
            urn = f"urn:li:person:{person_id}"
            print(f"[{label}] author_urn={urn}")
            return urn
        message = payload.get("message") or payload.get("error_description") or payload.get("serviceErrorCode")
        if message:
            print(f"[{label}] message={message}")
    elif payload:
        print(f"[{label}] message={payload}")
    return None


def main() -> None:
    token_fingerprint = hashlib.sha256(settings.LINKEDIN_ACCESS_TOKEN.encode()).hexdigest()[:12]
    print({
        "linkedin_access_token_set": bool(settings.LINKEDIN_ACCESS_TOKEN),
        "linkedin_access_token_len": len(settings.LINKEDIN_ACCESS_TOKEN),
        "linkedin_access_token_sha256_12": token_fingerprint if settings.LINKEDIN_ACCESS_TOKEN else "",
        "linkedin_author_urn": settings.LINKEDIN_AUTHOR_URN,
        "linkedin_visibility": settings.LINKEDIN_VISIBILITY,
        "dry_run": settings.DRY_RUN,
    })
    if not settings.LINKEDIN_ACCESS_TOKEN:
        raise SystemExit("Set LINKEDIN_ACCESS_TOKEN in .env first.")

    print("\nTrying identity endpoints...")
    userinfo_urn = _print_profile_result(
        "v2/userinfo minimal",
        *_get("https://api.linkedin.com/v2/userinfo"),
    )
    userinfo_versioned_urn = _print_profile_result(
        "v2/userinfo versioned",
        *_get("https://api.linkedin.com/v2/userinfo", versioned=True),
    )
    me_urn = _print_profile_result(
        "v2/me restli",
        *_get("https://api.linkedin.com/v2/me", restli=True),
    )
    me_versioned_urn = _print_profile_result(
        "v2/me versioned",
        *_get("https://api.linkedin.com/v2/me", restli=True, versioned=True),
    )

    urn = userinfo_urn or userinfo_versioned_urn or me_urn or me_versioned_urn
    if urn:
        print(f"\nPut this in .env:\nLINKEDIN_AUTHOR_URN={urn}")
    else:
        print("\nCould not derive author URN from this token.")
        print("Regenerate the token with identity scope plus w_member_social.")
        print("Recommended scopes for personal posting setup: openid profile w_member_social")


if __name__ == "__main__":
    main()

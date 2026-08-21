"""
🚀 PUBLISHER — публикация в LinkedIn с указанием источника.

Каждый пост в конце получает «🔗 Дереккөз: {source_name}» — повышает
доверие и защищает от ощущения, что новость выдумана.

DRY_RUN=1 — ничего не отправляет, только печатает финальный текст.
"""
import requests
from html.parser import HTMLParser
from urllib.parse import urljoin

from config import settings
from core import db

UGC_URL = "https://api.linkedin.com/v2/ugcPosts"
REST_POSTS_URL = "https://api.linkedin.com/rest/posts"
REST_IMAGES_URL = "https://api.linkedin.com/rest/images?action=initializeUpload"
ALLOWED_VISIBILITY = {"PUBLIC", "CONNECTIONS"}
IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/gif"}
REQUEST_HEADERS = {"User-Agent": "KazTechNewsroom/1.0 (+link preview)"}


class _MetaImageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "meta":
            return
        data = {key.lower(): value for key, value in attrs if key and value}
        name = (data.get("property") or data.get("name") or "").lower()
        if name in {"og:image", "og:image:secure_url", "twitter:image"} and data.get("content"):
            self.images.append(data["content"])


def compose_text(post: dict) -> str:
    parts = [post["body"].strip()]
    if post.get("cta"):
        parts.append(post["cta"].strip())
    src = post.get("source_name")
    if src:
        line = f"🔗 Дереккөз: {src}"
        if post.get("source_url"):
            line += f"\n{post['source_url']}"
        parts.append(line)
    return "\n\n".join(parts)


def _ugc_headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.LINKEDIN_ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }


def _rest_headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.LINKEDIN_ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
        "Linkedin-Version": settings.LINKEDIN_API_VERSION,
    }


def _validate_visibility() -> str:
    visibility = settings.LINKEDIN_VISIBILITY
    if visibility not in ALLOWED_VISIBILITY:
        raise ValueError("LINKEDIN_VISIBILITY must be PUBLIC or CONNECTIONS")
    return visibility


def _payload(text: str, post: dict | None = None) -> dict:
    visibility = _validate_visibility()

    source_url = (post or {}).get("source_url", "")
    content = {
        "shareCommentary": {"text": text},
        "shareMediaCategory": "NONE",
    }
    if source_url:
        content = {
            "shareCommentary": {"text": text},
            "shareMediaCategory": "ARTICLE",
            "media": [{
                "status": "READY",
                "originalUrl": source_url,
                "title": {"text": (post or {}).get("title") or (post or {}).get("source_name", "")},
                "description": {"text": (post or {}).get("source_name", "")},
            }],
        }

    return {
        "author": settings.LINKEDIN_AUTHOR_URN,
        "lifecycleState": "PUBLISHED",
        "specificContent": {"com.linkedin.ugc.ShareContent": content},
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": visibility},
    }


def _rest_payload(text: str, post: dict | None = None) -> dict:
    visibility = _validate_visibility()
    payload = {
        "author": settings.LINKEDIN_AUTHOR_URN,
        "commentary": text,
        "visibility": visibility,
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }

    source_url = (post or {}).get("source_url", "")
    if source_url:
        payload["content"] = {
            "article": {
                "source": source_url,
                "title": (post or {}).get("title") or (post or {}).get("source_name", ""),
                "description": (post or {}).get("source_name", ""),
            },
        }
    return payload


def _find_source_image_url(source_url: str) -> str | None:
    if not source_url:
        return None
    resp = requests.get(source_url, headers=REQUEST_HEADERS, timeout=20)
    resp.raise_for_status()
    parser = _MetaImageParser()
    parser.feed(resp.text[:200000])
    if not parser.images:
        return None
    return urljoin(source_url, parser.images[0])


def _download_image(image_url: str) -> tuple[bytes, str]:
    resp = requests.get(image_url, headers=REQUEST_HEADERS, timeout=30)
    resp.raise_for_status()
    content_type = resp.headers.get("Content-Type", "").split(";", 1)[0].lower()
    if content_type not in IMAGE_CONTENT_TYPES:
        raise ValueError(f"unsupported image content type: {content_type}")
    return resp.content, content_type


def _upload_image(image_bytes: bytes, content_type: str) -> str:
    init_resp = requests.post(
        REST_IMAGES_URL,
        headers=_rest_headers(),
        json={"initializeUploadRequest": {"owner": settings.LINKEDIN_AUTHOR_URN}},
        timeout=20,
    )
    init_resp.raise_for_status()
    value = init_resp.json()["value"]
    upload_url = value["uploadUrl"]
    image_urn = value["image"]

    upload_resp = requests.put(
        upload_url,
        headers={"Content-Type": content_type},
        data=image_bytes,
        timeout=60,
    )
    if upload_resp.status_code == 405:
        upload_resp = requests.post(
            upload_url,
            headers={"Content-Type": content_type},
            data=image_bytes,
            timeout=60,
        )
    upload_resp.raise_for_status()
    return image_urn


def _source_image_urn(post: dict) -> str | None:
    if settings.LINKEDIN_IMAGE_MODE != "source":
        return None
    try:
        image_url = _find_source_image_url(post.get("source_url", ""))
        if not image_url:
            print("[publisher] source image not found; falling back to article preview")
            return None
        image_bytes, content_type = _download_image(image_url)
        image_urn = _upload_image(image_bytes, content_type)
        print(f"[publisher] uploaded source image: {image_urn}")
        return image_urn
    except Exception as exc:
        print(f"[publisher] source image upload failed; falling back to article preview: {exc}")
        return None


def publish_post(post_id: int) -> str | None:
    post = db.get_post(post_id)
    if not post:
        raise ValueError(f"post {post_id} не найден")
    text = compose_text(post)

    if not settings.LINKEDIN_ENABLED:
        print("[publisher] LINKEDIN_ENABLED=0 — пропускаем LinkedIn.")
        return None

    if settings.DRY_RUN:
        print("[publisher] DRY_RUN — не отправлено. Финальный текст:\n")
        print(text)
        print("\n[publisher] (DRY_RUN=0 в .env — чтобы публиковать реально)")
        return None

    if not settings.LINKEDIN_ACCESS_TOKEN or not settings.LINKEDIN_AUTHOR_URN:
        raise RuntimeError("LinkedIn креды не заданы (см. .env).")

    if settings.LINKEDIN_POST_API == "rest":
        payload = _rest_payload(text, post)
        image_urn = _source_image_urn(post)
        if image_urn:
            payload["content"] = {"media": {"id": image_urn, "altText": post.get("title", "")}}
        resp = requests.post(REST_POSTS_URL, headers=_rest_headers(), json=payload, timeout=20)
    elif settings.LINKEDIN_POST_API == "ugc":
        resp = requests.post(UGC_URL, headers=_ugc_headers(), json=_payload(text, post), timeout=20)
    else:
        raise ValueError("LINKEDIN_POST_API must be rest or ugc")
    resp.raise_for_status()
    urn = resp.headers.get("x-restli-id") or resp.json().get("id")
    db.mark_published(post_id, urn)
    print(f"[publisher] опубликовано: {urn}")
    return urn

# TODO (фаза 2): загрузка картинки через registerUpload → shareMediaCategory=IMAGE.

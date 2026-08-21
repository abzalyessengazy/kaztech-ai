"""
🎨 VISUAL AGENT — 1 пост = 1 визуал.

Editor уже придумал image_prompt. Этот агент доводит промпт до
консистентного «фирменного» стиля страницы и (опционально) вызывает
генератор картинок.

Генерация изображений намеренно оставлена заглушкой (`generate_image`):
подключи любой провайдер (OpenAI Images, Google Imagen, Stability и т.д.)
одним методом — остальной пайплайн менять не нужно.
"""

# Единый визуальный почерк бренда — делает ленту узнаваемой.
BRAND_VISUAL_STYLE = (
    "flat editorial illustration, limited palette (deep teal, warm sand, off-white), "
    "subtle Kazakh ornament motif in the background, clean vector shapes, "
    "gentle irony, no text baked into the image, 1200x627 landscape for LinkedIn"
)


def build_prompt(image_idea: str) -> str:
    """Собирает финальный промпт: идея редактора + фирменный стиль."""
    idea = image_idea.strip() or "an AI robot reading tech news, looking overwhelmed"
    return f"{idea}. Style: {BRAND_VISUAL_STYLE}."


def generate_image(prompt: str, out_path: str = "post_image.png") -> str | None:
    """
    ЗАГЛУШКА. Верни путь к файлу после интеграции провайдера.

    Пример (псевдокод):
        img = images_client.generate(prompt=prompt, size="1200x627")
        img.save(out_path); return out_path

    Пока возвращает None — пайплайн опубликует пост без картинки,
    а промпт останется в БД, чтобы сгенерировать вручную.
    """
    print(f"[visual] промпт готов (генерация не подключена):\n  {prompt}")
    return None


def run(post: dict) -> dict:
    post["image_prompt"] = build_prompt(post.get("image_prompt", ""))
    post["image_path"] = generate_image(post["image_prompt"])
    return post

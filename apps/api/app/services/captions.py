"""Per-platform caption transforms + validation.

Platforms: linkedin (real), facebook / twitter / youtube (demo publishers for now).
Deterministic transforms; swap for an LLM later.
"""

LIMITS = {
    "linkedin": {"caption_max": 3000, "photos_max": 9},
    "facebook": {"caption_max": 63206, "photos_max": 10},
    "twitter":  {"caption_max": 280, "photos_max": 4},
    "youtube":  {"caption_max": 5000, "title_max": 100, "photos_max": 0},
}

SUPPORTED_PLATFORMS = list(LIMITS.keys())


def _first_line(master: str, max_len: int = 100) -> str:
    if not master:
        return ""
    line = master.splitlines()[0]
    return line[: max_len - 3] + "..." if len(line) > max_len else line


def generate_captions(master: str, platforms: list[str]) -> dict[str, dict]:
    master = (master or "").strip()
    out: dict[str, dict] = {}
    for p in platforms:
        if p == "twitter":
            cap = master if len(master) <= 280 else master[:277] + "..."
            out[p] = {"caption": cap, "title": ""}
        elif p == "youtube":
            out[p] = {"caption": master, "title": _first_line(master, LIMITS["youtube"]["title_max"])}
        else:  # linkedin, facebook
            out[p] = {"caption": master, "title": ""}
    return out


def validate_target(platform: str, caption: str, title: str = "",
                    photo_count: int = 0, has_video: bool = False) -> list[str]:
    errors: list[str] = []
    limits = LIMITS.get(platform)
    if not limits:
        return [f"unsupported platform: {platform}"]
    if len(caption or "") > limits["caption_max"]:
        errors.append(f"caption exceeds {limits['caption_max']} characters for {platform}")
    if photo_count > limits.get("photos_max", 99):
        errors.append(f"{platform} supports up to {limits.get('photos_max')} photos per post")

    if platform == "linkedin":
        if has_video:
            errors.append("LinkedIn video upload is coming soon — post photos or text for now")
        if not (caption or "").strip() and photo_count == 0:
            errors.append("linkedin post needs text or at least one photo")
    elif platform in ("facebook", "twitter"):
        if not (caption or "").strip() and photo_count == 0 and not has_video:
            errors.append(f"{platform} post needs text or media")
    elif platform == "youtube":
        if not title:
            errors.append("youtube requires a title")
        if not has_video:
            errors.append("youtube requires a video file")
    return errors

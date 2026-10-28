"""Plain data objects for editable pages, plus the text/image helpers that build them. No Django imports.

They are frozen dataclasses of simple types, so they pickle cleanly into the cache and templates only read them.
"""
import re
from dataclasses import dataclass, field

# CSS object-position, e.g. "50% 45%" or "center top". Strict, because the value is placed in a style attribute.
POSITION_RE = re.compile(r"^(\d{1,3}%|left|right|center|top|bottom)( (\d{1,3}%|left|right|center|top|bottom))?$")
DEFAULT_POSITION = "50% 45%"


@dataclass(frozen=True)
class ImageData:
    src: str            # the largest optimised size (fallback for old browsers)
    srcset: str         # "url 640w, url 1280w, ..."  (empty when only the original exists)
    position: str
    width: int = 0
    height: int = 0
    alt: str = ""          # describe meaningful photos; header photos are decorative and keep this empty


@dataclass(frozen=True)
class BlockData:
    heading: str
    items: tuple        # (("p", "text"), ("ul", ("line", "line")), ...) in reading order
    callout: bool = False


@dataclass(frozen=True)
class PageData:
    slug: str
    title: str
    crumb: str
    intro: str = ""
    eyebrow: str = ""
    paragraphs: tuple = ()
    header: ImageData | None = None
    side: ImageData | None = None
    blocks: tuple = field(default_factory=tuple)


def paragraphs(text: str) -> tuple:
    """Blank line = new paragraph. Single newlines inside a paragraph are kept as spaces."""
    parts = re.split(r"\n\s*\n", (text or "").replace("\r\n", "\n").strip())
    return tuple(" ".join(l.strip() for l in p.split("\n") if l.strip()) for p in parts if p.strip())


def block_items(text: str) -> tuple:
    """Paragraphs and bullet lists. Lines starting with '- ' or '* ' become a bullet list."""
    items, para, bullets = [], [], []

    def flush_para():
        if para:
            items.append(("p", " ".join(para)))
            para.clear()

    def flush_bullets():
        if bullets:
            items.append(("ul", tuple(bullets)))
            bullets.clear()

    for raw in (text or "").replace("\r\n", "\n").split("\n"):
        line = raw.strip()
        if not line:
            flush_para()
            flush_bullets()
        elif line[:2] in ("- ", "* "):
            flush_para()
            bullets.append(line[2:].strip())
        else:
            flush_bullets()
            para.append(line)
    flush_para()
    flush_bullets()
    return tuple(items)


def image_data(original_url, variants, url_for, position=DEFAULT_POSITION, alt=""):
    """Build ImageData from the stored original URL and the optimised variants [{"w", "h", "path"}].
    Returns None when there is no image at all."""
    pos = position if POSITION_RE.match(position or "") else DEFAULT_POSITION
    usable = sorted((v for v in (variants or []) if v.get("path") and v.get("w")), key=lambda v: v["w"])
    if usable:
        big = usable[-1]
        return ImageData(src=url_for(big["path"]), position=pos, width=big["w"], height=big.get("h", 0),
                         srcset=", ".join(f"{url_for(v['path'])} {v['w']}w" for v in usable), alt=alt)
    if original_url:
        return ImageData(src=original_url, srcset="", position=pos, alt=alt)
    return None

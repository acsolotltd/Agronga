"""Turns an uploaded photo into small, fast WebP sizes. Pillow only; storage is injected so it is easy to test.

Why: a 4 MB phone photo as a page header would be the slowest thing on the page. We keep the original (for re-processing),
serve 2-3 WebP sizes through srcset, strip EXIF/GPS data, and put a content hash in each file name so browsers and CDNs can
cache the files forever (a new upload gets new URLs).
"""
import hashlib
import io
import logging

from PIL import Image, ImageOps, UnidentifiedImageError

log = logging.getLogger(__name__)
HEADER_WIDTHS = (640, 1280, 1920)
SIDE_WIDTHS = (480, 960)
MAX_PIXELS = 40_000_000                      # refuse decompression bombs
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


class ImageError(Exception):
    pass


def build_variants(data: bytes, stem: str, save, widths=HEADER_WIDTHS, quality=78, directory="pages/v"):
    """data: original file bytes. save(path, bytes) -> stored path. Returns [{"w", "h", "path"}] smallest first.
    Never upscales: an 1000 px original yields 640 and 1000 px sizes."""
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as e:
        raise ImageError(f"unreadable image: {e}") from e
    img = ImageOps.exif_transpose(img)                      # honour the camera's rotation, then drop all metadata
    if img.mode in ("RGBA", "LA", "P"):
        rgba = img.convert("RGBA")
        flat = Image.new("RGB", rgba.size, (255, 255, 255))
        flat.paste(rgba, mask=rgba.split()[-1])
        img = flat
    elif img.mode != "RGB":
        img = img.convert("RGB")

    digest = hashlib.sha1(data).hexdigest()[:8]
    sizes = sorted({w for w in widths if w < img.width} | {min(img.width, max(widths))})
    out = []
    for w in sizes:
        h = max(1, round(img.height * w / img.width))
        frame = img if w == img.width else img.resize((w, h), Image.LANCZOS)
        buf = io.BytesIO()
        frame.save(buf, "WEBP", quality=quality, method=6)
        out.append({"w": w, "h": h, "path": save(f"{directory}/{stem}-{digest}-{w}.webp", buf.getvalue())})
    return out


def from_field(field_file, stem, widths):
    """Build variants for a Django FieldFile using the default storage. Never raises: a bad file just means no variants,
    and the page falls back to the original upload."""
    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage
    try:
        field_file.open("rb")
        try:
            data = field_file.read()
        finally:
            field_file.close()
        return build_variants(data, stem, lambda p, b: default_storage.save(p, ContentFile(b)), widths)
    except Exception:                                       # noqa: BLE001
        log.exception("Could not optimise %s", getattr(field_file, "name", "?"))
        return []


def delete(variants):
    from django.core.files.storage import default_storage
    for v in variants or []:
        try:
            default_storage.delete(v["path"])
        except Exception:                                   # noqa: BLE001
            log.warning("Could not delete %s", v.get("path"))

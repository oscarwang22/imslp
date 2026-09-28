from __future__ import annotations

import os
import tempfile
from pathlib import Path


def compress_ccitt_g4(source: Path, destination: Path, *, dpi: int = 300, threshold: int = 190) -> None:
    """Rasterise every page to 1-bit and embed lossless CCITT Group 4 TIFF strips.

    This deliberately trades selectable text and colour for a predictable archival representation.
    The source file should be retained until this function and validation both succeed.
    """
    try:
        import fitz
        import img2pdf
        from PIL import Image
    except ImportError as error:  # pragma: no cover - installation concern
        raise RuntimeError("compression extras are missing; install the project dependencies") from error

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="score-curator-") as temp_name:
        temp = Path(temp_name)
        pages: list[Path] = []
        document = fitz.open(source)
        try:
            if document.page_count == 0:
                raise ValueError("input PDF has no pages")
            scale = dpi / 72
            for index, page in enumerate(document):
                pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), colorspace=fitz.csGRAY, alpha=False)
                image = Image.frombytes("L", (pixmap.width, pixmap.height), pixmap.samples)
                # A fixed threshold is deterministic and avoids dithering noise that hurts compression.
                mono = image.point(lambda value: 255 if value >= threshold else 0, mode="1")
                page_path = temp / f"page-{index + 1:05d}.tiff"
                mono.save(page_path, format="TIFF", compression="group4", dpi=(dpi, dpi))
                pages.append(page_path)
        finally:
            document.close()

        partial = destination.with_suffix(destination.suffix + ".partial")
        partial.write_bytes(img2pdf.convert([str(page) for page in pages], dpi=dpi))
        validate_ccitt_g4(partial, expected_pages=len(pages))
        os.replace(partial, destination)


def validate_ccitt_g4(path: Path, expected_pages: int | None = None) -> None:
    from pypdf import PdfReader
    from pypdf.generic import ArrayObject

    reader = PdfReader(path)
    if expected_pages is not None and len(reader.pages) != expected_pages:
        raise ValueError(f"page count changed: expected {expected_pages}, got {len(reader.pages)}")
    if not reader.pages:
        raise ValueError("compressed PDF has no pages")
    for number, page in enumerate(reader.pages, 1):
        images = page.get("/Resources", {}).get("/XObject", {})
        if not images:
            raise ValueError(f"page {number} has no image object")
        for obj in images.values():
            image = obj.get_object()
            if image.get("/Subtype") != "/Image":
                continue
            filters = image.get("/Filter")
            filters = list(filters) if isinstance(filters, ArrayObject) else [filters]
            if "/CCITTFaxDecode" not in {str(item) for item in filters}:
                raise ValueError(f"page {number} contains a non-CCITT image")
            params = image.get("/DecodeParms") or {}
            if isinstance(params, ArrayObject):
                params = next((p for p in params if p), {})
            if int(params.get("/K", 0)) != -1:
                raise ValueError(f"page {number} is CCITT but not Group 4 (K=-1)")

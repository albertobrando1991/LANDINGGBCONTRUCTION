"""Asset condivisi dai documenti commerciali GB Construction."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image as PilImage
from reportlab.lib.units import mm
from reportlab.platypus import Image

ASSETS_PATH = Path(__file__).resolve().parent / "assets"
LOGO_PATH = ASSETS_PATH / "email-logo.png"
COVER_PATH = ASSETS_PATH / "document-cover.jpg"
FIRMA_PATH = ASSETS_PATH / "gb-timbro-firma.png"


def is_gb_tenant(tenant: dict) -> bool:
    return "gbconstruction" in str(tenant.get("slug") or "").lower()


def firma_appaltatrice(tenant: dict, *, width: float = 67 * mm) -> Image | None:
    """Restituisce timbro e firma privi del margine trasparente della scansione.

    Il file originale resta intatto: il ritaglio viene creato soltanto in memoria
    mentre si compone il PDF.
    """
    if not is_gb_tenant(tenant) or not FIRMA_PATH.exists():
        return None

    with PilImage.open(FIRMA_PATH) as source:
        image = source.convert("RGBA")
        alpha = image.getchannel("A")
        bbox = alpha.getbbox()
        if bbox:
            image = image.crop(bbox)
        output = io.BytesIO()
        image.save(output, format="PNG", optimize=True)
        output.seek(0)
        ratio = image.height / image.width

    flowable = Image(output, width=width, height=width * ratio)
    # ReportLab legge lo stream in fase di build: manteniamo un riferimento
    # esplicito fino alla chiusura del documento.
    flowable._gb_source = output
    return flowable

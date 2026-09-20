"""
QR code rendering for share links (2026-09-20, see docs/decisions.md).

Generated server-side as an SVG rather than a PNG - no Pillow/native
image dependency needed (qrcode's SVG factories use the standard
library's XML tools), and an SVG scales cleanly at any display size a
phone camera might be held at. Returned as a data: URI so the frontend
can drop it straight into an <img src=...> with no extra request and
no file to store or clean up - the QR just encodes the share URL,
which the backend already knows how to regenerate from the token at
any time.
"""

import base64
import io

import qrcode
import qrcode.image.svg


def qr_svg_data_uri(data: str) -> str:
    img = qrcode.make(
        data,
        image_factory=qrcode.image.svg.SvgPathImage,
        box_size=8,
        border=2,
    )
    buf = io.BytesIO()
    img.save(buf)
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"

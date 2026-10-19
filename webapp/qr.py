# qr code image for share links

import base64
import io

import qrcode
import qrcode.image.svg


# qr code for a url as an svg data uri
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

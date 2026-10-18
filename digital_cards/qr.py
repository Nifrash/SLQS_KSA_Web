"""Deterministic QR rendering; never store QR images in public media."""
from io import BytesIO
import qrcode


def qr_png_bytes(text):
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,
                       box_size=8, border=4)
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#102d44", back_color="white").convert("RGB")
    stream = BytesIO()
    img.save(stream, format="PNG")
    return stream.getvalue()

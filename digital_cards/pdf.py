"""Printable digital member card PDF generated in memory, not public MEDIA_ROOT."""
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from PIL import Image
from .qr import qr_png_bytes

NAVY = (0.055, 0.149, 0.235)
GOLD = (0.78, 0.60, 0.29)
WHITE = (1, 1, 1)


def _text_fit(c, text, x, y, max_width, font="Helvetica-Bold", size=12, minimum=7):
    text = str(text or "")
    while size > minimum and stringWidth(text, font, size) > max_width:
        size -= .5
    if stringWidth(text, font, size) > max_width:
        while text and stringWidth(text + "...", font, size) > max_width:
            text = text[:-1]
        text += "..."
    c.setFont(font, size)
    c.drawString(x, y, text)


def card_pdf_bytes(card, verification_link):
    """Generate a landscape printable single-card PDF (~86 x 54 mm, at 1.3x scale)."""
    width, height = 345, 218
    stream = BytesIO()
    pdf = canvas.Canvas(stream, pagesize=(width, height), pageCompression=1)
    pdf.setTitle("SLQS KSA Digital Membership Card")
    pdf.setAuthor("Sri Lankan Quantity Surveyors - Saudi Arabia")
    pdf.setFillColorRGB(*NAVY)
    pdf.roundRect(0, 0, width, height, 12, fill=1, stroke=0)
    pdf.setFillColorRGB(*GOLD)
    pdf.rect(0, height-7, width, 7, fill=1, stroke=0)
    pdf.setStrokeColorRGB(*GOLD)
    pdf.line(18, 158, width-18, 158)
    pdf.setFillColorRGB(*WHITE)
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawString(19, 177, "SLQS")
    pdf.setFont("Helvetica", 8)
    pdf.drawString(100, 187, "SRI LANKAN QUANTITY SURVEYORS")
    pdf.drawString(100, 175, "SAUDI ARABIA")

    app = card.member.application
    pdf.setFillColorRGB(*GOLD)
    pdf.setFont("Helvetica", 8)
    pdf.drawString(19, 140, "DIGITAL MEMBERSHIP CARD")
    pdf.setFillColorRGB(*WHITE)
    _text_fit(pdf, app.full_name, 19, 121, 207, size=15)
    _text_fit(pdf, app.job_title, 19, 103, 207, font="Helvetica", size=9)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(19, 80, card.member.membership_number)
    pdf.setFont("Helvetica", 8)
    pdf.drawString(19, 63, "Joined: " + card.member.joined_on.strftime("%d %b %Y"))
    due = card.member.renewal_due_on
    pdf.drawString(19, 50, "Renewal due: " + (due.strftime("%d %b %Y") if due else "Not assigned"))
    pdf.setFillColorRGB(*GOLD)
    pdf.drawString(19, 24, "Verify live status by scanning QR")

    # Include the linked account's optional portrait only on the private PDF;
    # the public QR verification page never displays a member photograph.
    try:
        user = card.member.application.user
        account = user.slqs_account if user else None
        if account and account.profile_photo:
            with account.profile_photo.open("rb") as file:
                portrait = Image.open(file)
                portrait.load()
                portrait = portrait.convert("RGB")
                portrait.thumbnail((300, 400))
                pdf.drawImage(ImageReader(portrait), 190, 59, width=42, height=53,
                              preserveAspectRatio=True, anchor="c", mask="auto")
    except (OSError, ValueError, AttributeError):
        # A missing/corrupt optional portrait should not block card generation.
        pass

    qr_bytes = qr_png_bytes(verification_link)
    pdf.setFillColorRGB(*WHITE)
    pdf.roundRect(242, 43, 91, 91, 4, fill=1, stroke=0)
    pdf.drawImage(ImageReader(BytesIO(qr_bytes)), 246, 47, 83, 83)
    pdf.setFillColorRGB(*WHITE)
    pdf.setFont("Helvetica", 7)
    pdf.drawCentredString(287, 33, "SCAN TO VERIFY")
    pdf.showPage()
    pdf.save()
    return stream.getvalue()

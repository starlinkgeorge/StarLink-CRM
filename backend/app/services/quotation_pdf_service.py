from io import BytesIO
import ipaddress
from os import getenv
from pathlib import Path
import re
import socket
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.config import get_settings
from app.models.customer import Customer
from app.models.quotation import Quotation, QuotationItem, QuotationVersion


BRAND_BLUE = colors.HexColor("#153A5B")
LIGHT_BLUE = colors.HexColor("#EAF1F7")
TEXT_GREY = colors.HexColor("#64748B")
INK = colors.HexColor("#172033")
BORDER_GREY = colors.HexColor("#D7DEE7")
STARLINK_LOGO_PATH = Path(__file__).resolve().parents[1] / "assets" / "starlink-logo.png"
# The supplied source image includes a 34 px transparent/white inset before
# the first coloured pixel (source width: 644 px).  Compensating for that
# inset at draw time aligns the *visible* wordmark, rather than the image
# canvas, to the company details below it.  Keeping the original asset intact
# also avoids changing its use outside this PDF template.
STARLINK_LOGO_VISIBLE_LEFT_INSET = (34 / 644) * (52 * mm)

# The 159 mm quotation tables are centered inside SimpleDocTemplate's frame.
# ReportLab reserves 6 pt on each side of that frame, so a title paragraph
# needs this calculated offset to start on the exact same vertical grid line.
QUOTATION_GRID_WIDTH = 159 * mm
QUOTATION_GRID_LEFT_OFFSET = ((A4[0] - (36 * mm) - 12) - QUOTATION_GRID_WIDTH) / 2


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def _fetch_public_image(url: str | None) -> bytes | None:
    if not url:
        return None
    url = _normalise_catalog_image_url(url)
    local_data = _read_catalog_image(url)
    if local_data is not None:
        return local_data
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443)
        for address in addresses:
            ip = ipaddress.ip_address(address[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return None
        request = Request(url, headers={"User-Agent": "StarLink-CRM-Quotation/3.0"})
        with build_opener(_NoRedirect()).open(request, timeout=4) as response:
            content_type = response.headers.get_content_type()
            if not content_type.startswith("image/"):
                return None
            data = response.read(5_000_001)
            return data if len(data) <= 5_000_000 else None
    except (OSError, ValueError):
        return None


def _normalise_catalog_image_url(url: str) -> str:
    """Point legacy product-image URLs at the configured public catalogue host."""
    parsed = urlparse(url)
    if not parsed.path.startswith("/product-images/"):
        return url
    configured_base = get_settings()["product_image_base_url"]
    if not configured_base:
        return url
    filename = Path(parsed.path).name
    if not re.fullmatch(r"[A-Za-z0-9_-]+\.(?:jpe?g|png|webp)", filename, re.IGNORECASE):
        return url
    return f"{configured_base}/{filename}"


def _read_catalog_image(url: str) -> bytes | None:
    """Read catalogue images copied into the backend image.

    Older product records can contain a local frontend URL. A backend container
    cannot fetch its host loopback address, so only the known product-images
    path is mapped to a local, bounded directory before public URL fetching.
    """
    parsed = urlparse(url)
    if not parsed.path.startswith("/product-images/"):
        return None
    filename = Path(parsed.path).name
    if not re.fullmatch(r"[A-Za-z0-9_-]+\.(?:jpe?g|png|webp)", filename, re.IGNORECASE):
        return None

    roots = [
        Path(getenv("PRODUCT_IMAGE_DIR", "/app/product-images")),
        Path(__file__).resolve().parents[2] / "product-images",
        Path(__file__).resolve().parents[3] / "frontend" / "public" / "product-images",
    ]
    for root in roots:
        try:
            resolved_root = root.resolve()
            candidate = (resolved_root / filename).resolve()
            if candidate.parent != resolved_root or not candidate.is_file():
                continue
            data = candidate.read_bytes()
            if len(data) <= 5_000_000:
                return data
        except OSError:
            continue
    return None


def _picture(url: str | None):
    picture_size = 18 * mm
    data = _fetch_public_image(url)
    if data:
        try:
            image = Image(BytesIO(data), width=picture_size, height=picture_size, kind="proportional")
            image.hAlign = "CENTER"
            return image
        except Exception:  # ReportLab supports several image types; invalid content uses placeholder.
            pass
    drawing = Drawing(picture_size, picture_size)
    drawing.add(
        Rect(
            0,
            0,
            picture_size,
            picture_size,
            fillColor=colors.HexColor("#F1F5F9"),
            strokeColor=colors.HexColor("#CBD5E1"),
        )
    )
    drawing.add(
        String(
            picture_size / 2,
            picture_size / 2 - 1,
            "No image",
            textAnchor="middle",
            fontSize=7,
            fillColor=TEXT_GREY,
        )
    )
    return drawing


def _brand_logo():
    """Return the packaged StarLink logo, with a graceful print-safe fallback."""
    width = 52 * mm
    height = 11.55 * mm
    if STARLINK_LOGO_PATH.is_file():
        try:
            logo = Image(str(STARLINK_LOGO_PATH), width=width, height=height)
            logo.hAlign = "LEFT"
            # ReportLab aligns the image canvas.  Shift its source canvas left
            # by the known internal border so the coloured STARLINK mark shares
            # the exact left edge of the company-name paragraph below it.
            logo._offs_x = -STARLINK_LOGO_VISIBLE_LEFT_INSET
            return logo
        except OSError:
            pass

    drawing = Drawing(width, height)
    drawing.add(
        String(
            0,
            2.5 * mm,
            "STARLINK",
            fontName="Helvetica-Bold",
            fontSize=18,
            fillColor=BRAND_BLUE,
        )
    )
    return drawing


def _money(value) -> str:  # Decimal-compatible formatting.
    return f"{value:,.2f}"


def _safe_text(value: str | None, fallback: str = "-") -> str:
    return escape(value.strip()) if value and value.strip() else fallback


def _footer(canvas, document, company_name: str, quotation_number: str) -> None:  # noqa: ANN001
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#D7DEE7"))
    canvas.line(18 * mm, 14 * mm, A4[0] - 18 * mm, 14 * mm)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(TEXT_GREY)
    canvas.drawString(18 * mm, 9 * mm, f"{company_name} | {quotation_number}")
    canvas.drawRightString(A4[0] - 18 * mm, 9 * mm, f"Page {document.page}")
    canvas.restoreState()


def quotation_filename(quotation_number: str, version_no: int) -> str:
    """Return an internal immutable-snapshot filename for local storage."""
    safe_number = re.sub(r"[^A-Za-z0-9_-]", "_", quotation_number)
    return f"{safe_number}-V{version_no}.pdf"


def _render_quotation_pdf(
    quotation: Quotation,
    version: QuotationVersion,
    customer: Customer,
    output: str | BytesIO,
) -> None:
    settings = get_settings()

    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "StarLinkBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=INK,
    )
    small = ParagraphStyle("StarLinkSmall", parent=body, fontSize=7.5, leading=9)
    left = ParagraphStyle("StarLinkLeft", parent=body, alignment=TA_LEFT)
    right = ParagraphStyle("StarLinkRight", parent=body, alignment=TA_RIGHT)
    title = ParagraphStyle(
        "StarLinkTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=19,
        leading=22,
        alignment=TA_RIGHT,
        textColor=BRAND_BLUE,
    )
    company = ParagraphStyle(
        "StarLinkCompany",
        parent=body,
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=13,
        textColor=BRAND_BLUE,
    )
    contact = ParagraphStyle(
        "StarLinkContact",
        parent=small,
        leading=10,
        textColor=TEXT_GREY,
    )
    reference = ParagraphStyle(
        "StarLinkReference",
        parent=right,
        fontSize=8.5,
        leading=11,
        textColor=BRAND_BLUE,
    )
    section_label = ParagraphStyle(
        "StarLinkSectionLabel",
        parent=small,
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9,
        textColor=BRAND_BLUE,
    )
    center_small = ParagraphStyle("StarLinkCenter", parent=small, alignment=TA_CENTER)
    item_name = ParagraphStyle(
        "StarLinkItemName",
        parent=body,
        fontName="Helvetica-Bold",
        leading=10,
        alignment=TA_LEFT,
    )
    header_small = ParagraphStyle(
        "StarLinkTableHeader",
        parent=center_small,
        fontName="Helvetica-Bold",
        textColor=colors.white,
    )
    header_left = ParagraphStyle(
        "StarLinkTableHeaderLeft",
        parent=header_small,
        alignment=TA_LEFT,
    )
    header_right = ParagraphStyle(
        "StarLinkTableHeaderRight",
        parent=header_small,
        alignment=TA_RIGHT,
    )

    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=20 * mm,
        title=f"Quotation {quotation.quotation_number}",
        author=settings["company_name"],
    )
    alibaba_store = settings["company_alibaba_store"]
    company_website = settings["company_website"]
    email = settings["company_email"]
    whatsapp = settings["company_whatsapp"]
    story = []
    contact_text = (
        f"Alibaba Store: {_safe_text(alibaba_store)}<br/>"
        f"Company Website: {_safe_text(company_website)}<br/>"
        f"Email: {_safe_text(email)} &nbsp;|&nbsp; WhatsApp: {_safe_text(whatsapp)}"
    )
    reference_text = (
        f"Quotation No.: <b>{_safe_text(quotation.quotation_number)}</b>"
        f"<br/>Date: {version.created_at:%Y-%m-%d}"
    )
    story.append(
        Table(
            [
                [
                    _brand_logo(),
                    Paragraph("QUOTATION", title),
                ],
                [
                    [
                        Paragraph(_safe_text(settings["company_name"]), company),
                        Spacer(1, 1.2 * mm),
                        Paragraph(contact_text, contact),
                    ],
                    Paragraph(reference_text, reference),
                ],
            ],
            colWidths=[112 * mm, 47 * mm],
            style=TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, 0), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("LINEBELOW", (0, 1), (-1, 1), 1.2, BRAND_BLUE),
                    ("BOTTOMPADDING", (0, 1), (-1, 1), 7),
                ]
            ),
        )
    )
    story.append(Spacer(1, 6 * mm))
    story.append(Table([
        [Paragraph("QUOTATION TO", section_label), Paragraph("CUSTOMER CONTACT", section_label)],
        [
            Paragraph(
                f"<b>{_safe_text(customer.company_name)}</b>"
                f"<br/>{_safe_text(customer.country)}",
                body,
            ),
            Paragraph(
                f"Contact: {_safe_text(customer.contact_name)}"
                f"<br/>Email: {_safe_text(customer.email)}"
                f"<br/>WhatsApp: {_safe_text(customer.whatsapp)}",
                body,
            ),
        ],
    ], colWidths=[79.5 * mm, 79.5 * mm], style=TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), LIGHT_BLUE), ("TEXTCOLOR", (0, 0), (-1, 0), BRAND_BLUE),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER_GREY),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_GREY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("PADDING", (0, 0), (-1, -1), 7),
    ])))
    story.append(Spacer(1, 6 * mm))

    item_rows = [[
        Paragraph("Item Name", header_left), Paragraph("Picture", header_small),
        Paragraph("Unit Price", header_right), Paragraph("QTY", header_small),
        Paragraph("Total Price", header_right),
    ]]
    for item in version.items:
        item_rows.append([
            Paragraph(
                f"{_safe_text(item.product_name_snapshot)}<br/>"
                f"<font color='#64748B' size='7'>{_safe_text(item.sku_snapshot)}</font>",
                item_name,
            ),
            _picture(item.picture_snapshot),
            Paragraph(f"{version.currency} {_money(item.unit_price)}", right),
            Paragraph(f"{item.quantity:g}", center_small),
            Paragraph(f"{version.currency} {_money(item.line_total)}", right),
        ])
    item_table = Table(
        item_rows,
        colWidths=[57 * mm, 24 * mm, 29 * mm, 15 * mm, 34 * mm],
        repeatRows=1,
    )
    item_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), BRAND_BLUE),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (0, -1), "LEFT"),
                ("ALIGN", (1, 1), (1, -1), "CENTER"),
                ("ALIGN", (2, 1), (2, -1), "RIGHT"),
                ("ALIGN", (3, 1), (3, -1), "CENTER"),
                ("ALIGN", (4, 1), (4, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.5, BORDER_GREY),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#F8FAFC")],
                ),
                ("TOPPADDING", (0, 0), (-1, 0), 5),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
                ("TOPPADDING", (0, 1), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 3),
            ]
        )
    )
    story.append(item_table)
    story.append(Spacer(1, 5 * mm))
    amount_label = ParagraphStyle(
        "AmountLabel", parent=body, fontName="Helvetica-Bold", textColor=colors.white
    )
    amount_value = ParagraphStyle("AmountValue", parent=right, textColor=colors.white)
    story.append(
        Table(
            [
                [
                    Paragraph("Total cost", left),
                    Paragraph(f"{version.currency} {_money(version.subtotal)}", right),
                ],
                [
                    Paragraph("Door to door shipping cost", left),
                    Paragraph(f"{version.currency} {_money(version.shipping_cost)}", right),
                ],
                [
                    Paragraph("Amount", amount_label),
                    Paragraph(
                        f"<b>{version.currency} {_money(version.total_amount)}</b>",
                        amount_value,
                    ),
                ],
            ],
            # Use the same full-width grid as the customer, item, and terms
            # tables so the three financial rows form part of the quotation.
            colWidths=[104 * mm, 55 * mm],
            hAlign="CENTER",
            style=TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.5, BORDER_GREY),
                    ("LINEABOVE", (0, 1), (-1, -1), 0.5, BORDER_GREY),
                    ("BACKGROUND", (0, -1), (-1, -1), BRAND_BLUE),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            ),
        )
    )
    story.append(Spacer(1, 7 * mm))
    terms_heading = ParagraphStyle(
        "TermsHeading",
        parent=body,
        fontName="Helvetica-Bold",
        fontSize=10,
        leftIndent=QUOTATION_GRID_LEFT_OFFSET,
        textColor=BRAND_BLUE,
    )
    story.append(Paragraph("TERMS AND CONDITIONS", terms_heading))
    story.append(Spacer(1, 2 * mm))
    story.append(Table([
        [Paragraph("Validity", small), Paragraph(
            f"This quotation is valid for {version.validity_days} calendar days from the date of issue.", body
        )],
        [Paragraph("Payment Terms", small), Paragraph(
            f"Payment shall be made as follows: {_safe_text(version.payment_term)}.", body
        )],
        [Paragraph("Delivery Time", small), Paragraph(
            f"Estimated delivery time: {_safe_text(version.delivery_time)}, subject to final order confirmation and receipt of the required deposit.", body
        )],
    ], colWidths=[35 * mm, 124 * mm], style=TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), LIGHT_BLUE),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER_GREY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("PADDING", (0, 0), (-1, -1), 7),
    ])))

    document.build(
        story,
        onFirstPage=lambda canvas, document: _footer(
            canvas, document, settings["company_name"], quotation.quotation_number
        ),
        onLaterPages=lambda canvas, document: _footer(
            canvas, document, settings["company_name"], quotation.quotation_number
        ),
    )


def generate_quotation_pdf_bytes(
    quotation: Quotation,
    version: QuotationVersion,
    customer: Customer,
) -> bytes:
    """Render a quotation directly to memory for stateless serverless requests."""
    output = BytesIO()
    _render_quotation_pdf(quotation, version, customer, output)
    return output.getvalue()


def generate_quotation_pdf(
    quotation: Quotation,
    version: QuotationVersion,
    customer: Customer,
) -> tuple[Path, str]:
    """Compatibility writer used by local Docker development and manual export."""
    output_dir = Path(get_settings()["quotation_output_dir"]).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = quotation_filename(quotation.quotation_number, version.version_no)
    final_path = output_dir / filename
    temporary_path = output_dir / f".{filename}.tmp"
    _render_quotation_pdf(quotation, version, customer, str(temporary_path))
    temporary_path.replace(final_path)
    return final_path, f"/static/quotations/{filename}"

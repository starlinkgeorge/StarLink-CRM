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
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
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
TEXT_GREY = colors.HexColor("#4B5563")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def _fetch_public_image(url: str | None) -> bytes | None:
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    local_data = _read_catalog_image(url)
    if local_data is not None:
        return local_data
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


def _read_catalog_image(url: str) -> bytes | None:
    """Read catalogue images copied into the backend image.

    Product records currently store frontend URLs such as
    ``http://localhost:5173/product-images/SL-F-001.jpg``. A backend container
    cannot fetch its host's loopback URL, so only the known product-images path
    is mapped to a local, bounded directory before public URL fetching runs.
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
    data = _fetch_public_image(url)
    if data:
        try:
            return Image(BytesIO(data), width=24 * mm, height=24 * mm, kind="proportional")
        except Exception:  # ReportLab supports several image types; invalid content uses placeholder.
            pass
    drawing = Drawing(24 * mm, 24 * mm)
    drawing.add(
        Rect(
            0,
            0,
            24 * mm,
            24 * mm,
            fillColor=colors.HexColor("#F1F5F9"),
            strokeColor=colors.HexColor("#CBD5E1"),
        )
    )
    drawing.add(
        String(
            12 * mm,
            11 * mm,
            "No image",
            textAnchor="middle",
            fontSize=7,
            fillColor=TEXT_GREY,
        )
    )
    return drawing


def _money(value) -> str:  # Decimal-compatible formatting.
    return f"{value:,.2f}"


def _safe_text(value: str | None, fallback: str = "-") -> str:
    return escape(value.strip()) if value and value.strip() else fallback


def _footer(canvas, document, quotation_number: str) -> None:  # noqa: ANN001
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#D7DEE7"))
    canvas.line(18 * mm, 14 * mm, A4[0] - 18 * mm, 14 * mm)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(TEXT_GREY)
    canvas.drawString(18 * mm, 9 * mm, f"Dalian StarLink International Trade Co., Ltd. | {quotation_number}")
    canvas.drawRightString(A4[0] - 18 * mm, 9 * mm, f"Page {document.page}")
    canvas.restoreState()


def quotation_filename(quotation_number: str, version_no: int) -> str:
    safe_number = re.sub(r"[^A-Za-z0-9_-]", "_", quotation_number)
    return f"{safe_number}-V{version_no}.pdf"


def generate_quotation_pdf(
    quotation: Quotation,
    version: QuotationVersion,
    customer: Customer,
) -> tuple[Path, str]:
    settings = get_settings()
    output_dir = Path(settings["quotation_output_dir"]).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = quotation_filename(quotation.quotation_number, version.version_no)
    final_path = output_dir / filename
    temporary_path = output_dir / f".{filename}.tmp"

    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "StarLinkBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#1F2937"),
    )
    small = ParagraphStyle("StarLinkSmall", parent=body, fontSize=7.5, leading=9)
    right = ParagraphStyle("StarLinkRight", parent=body, alignment=TA_RIGHT)
    title = ParagraphStyle(
        "StarLinkTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=23,
        alignment=TA_RIGHT,
        textColor=BRAND_BLUE,
    )
    company = ParagraphStyle(
        "StarLinkCompany",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=17,
        textColor=BRAND_BLUE,
    )
    center_small = ParagraphStyle("StarLinkCenter", parent=small, alignment=TA_CENTER)
    header_small = ParagraphStyle(
        "StarLinkTableHeader",
        parent=center_small,
        fontName="Helvetica-Bold",
        textColor=colors.white,
    )

    document = SimpleDocTemplate(
        str(temporary_path),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=20 * mm,
        title=f"Quotation {quotation.quotation_number} V{version.version_no}",
        author="Dalian StarLink International Trade Co., Ltd.",
    )
    website = settings["company_website"] or "Not configured"
    email = settings["company_email"] or "Not configured"
    whatsapp = settings["company_whatsapp"] or "Not configured"
    story = []
    contact_text = (
        f"Website: {_safe_text(website)}<br/>Email: {_safe_text(email)}"
        f"<br/>WhatsApp: {_safe_text(whatsapp)}"
    )
    reference_text = (
        f"Quotation No.: <b>{_safe_text(quotation.quotation_number)}</b>"
        f"<br/>Version: <b>V{version.version_no}</b>"
        f"<br/>Date: {version.created_at:%Y-%m-%d}"
    )
    story.append(
        Table(
            [
                [
                    Paragraph("Dalian StarLink International Trade Co., Ltd.", company),
                    Paragraph("QUOTATION", title),
                ],
                [Paragraph(contact_text, small), Paragraph(reference_text, right)],
            ],
            colWidths=[112 * mm, 47 * mm],
            style=TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LINEBELOW", (0, 1), (-1, 1), 1.2, BRAND_BLUE),
                    ("BOTTOMPADDING", (0, 1), (-1, 1), 7),
                ]
            ),
        )
    )
    story.append(Spacer(1, 6 * mm))
    story.append(Table([
        [Paragraph("QUOTATION TO", small), Paragraph("CUSTOMER CONTACT", small)],
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
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#C9D4DF")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D7DEE7")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("PADDING", (0, 0), (-1, -1), 7),
    ])))
    story.append(Spacer(1, 6 * mm))

    item_rows = [[
        Paragraph("Item Name", header_small), Paragraph("Picture", header_small),
        Paragraph("Unit Price", header_small), Paragraph("QTY", header_small),
        Paragraph("Total Price", header_small),
    ]]
    for item in version.items:
        item_rows.append([
            Paragraph(
                f"<b>{_safe_text(item.product_name_snapshot)}</b>"
                f"<br/><font color='#64748B'>{_safe_text(item.sku_snapshot)}</font>",
                body,
            ),
            _picture(item.picture_snapshot),
            Paragraph(f"{version.currency} {_money(item.unit_price)}", right),
            Paragraph(f"{item.quantity:g}", center_small),
            Paragraph(f"{version.currency} {_money(item.line_total)}", right),
        ])
    item_table = Table(
        item_rows,
        colWidths=[60 * mm, 30 * mm, 26 * mm, 15 * mm, 28 * mm],
        repeatRows=1,
    )
    item_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), BRAND_BLUE),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 1), (1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#C9D4DF")),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#F8FAFC")],
                ),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
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
                    Paragraph("Total cost", body),
                    Paragraph(f"{version.currency} {_money(version.subtotal)}", right),
                ],
                [
                    Paragraph("Door to door shipping cost", body),
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
            colWidths=[55 * mm, 42 * mm],
            hAlign="RIGHT",
            style=TableStyle(
                [
                    ("GRID", (0, 0), (-1, -2), 0.5, colors.HexColor("#C9D4DF")),
                    ("BACKGROUND", (0, -1), (-1, -1), BRAND_BLUE),
                    ("PADDING", (0, 0), (-1, -1), 7),
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
        textColor=BRAND_BLUE,
    )
    story.append(Paragraph("TERMS", terms_heading))
    story.append(Spacer(1, 2 * mm))
    story.append(Table([
        [Paragraph("Validity", small), Paragraph(f"{version.validity_days} days", body)],
        [Paragraph("Payment Term", small), Paragraph(_safe_text(version.payment_term), body)],
        [Paragraph("Delivery Time", small), Paragraph(_safe_text(version.delivery_time), body)],
    ], colWidths=[35 * mm, 124 * mm], style=TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), LIGHT_BLUE),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#C9D4DF")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("PADDING", (0, 0), (-1, -1), 7),
    ])))

    footer = lambda canvas, doc: _footer(canvas, doc, quotation.quotation_number)
    document.build(story, onFirstPage=footer, onLaterPages=footer)
    temporary_path.replace(final_path)
    return final_path, f"/static/quotations/{filename}"

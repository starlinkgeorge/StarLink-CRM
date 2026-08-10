from datetime import datetime, timezone
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace

from openpyxl import load_workbook

from app.services.quotation_excel_service import (
    generate_quotation_excel,
    quotation_excel_filename,
)


def test_excel_export_keeps_editable_inputs_and_formula_totals() -> None:
    quotation = SimpleNamespace(quotation_number="SLQ-20260810-000001")
    customer = SimpleNamespace(
        company_name="Happy Kids Preschool",
        country="United States",
        contact_name="Maria",
        email="maria@example.com",
        whatsapp="+1 202 555 0100",
    )
    version = SimpleNamespace(
        version_no=1,
        created_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
        currency="USD",
        shipping_cost=Decimal("100.00"),
        validity_days=30,
        payment_term="30% deposit, balance before shipment",
        delivery_time="30-45 days after deposit",
        items=[
            SimpleNamespace(
                product_name_snapshot="Small Moon Table",
                sku_snapshot="SL-F-002",
                picture_snapshot=None,
                unit_price=Decimal("55.00"),
                quantity=Decimal("2.00"),
            ),
            SimpleNamespace(
                product_name_snapshot="Cleaning Set",
                sku_snapshot="SL-F-039",
                picture_snapshot=None,
                unit_price=Decimal("49.00"),
                quantity=Decimal("1.00"),
            ),
        ],
    )

    workbook_bytes = generate_quotation_excel(quotation, version, customer)
    workbook = load_workbook(BytesIO(workbook_bytes), data_only=False)
    sheet = workbook["Quotation"]

    assert sheet["A1"].value == "Dalian StarLink International Trade Co., Ltd."
    assert sheet["E10"].value == "=C10*D10"
    assert sheet["E11"].value == "=C11*D11"
    assert sheet["E13"].value == "=SUM(E10:E11)"
    assert sheet["E15"].value == "=E13+E14"
    assert sheet["C10"].fill.fgColor.rgb == "00FFF2CC"
    assert sheet["E14"].fill.fgColor.rgb == "00FFF2CC"
    assert workbook.calculation.fullCalcOnLoad is True
    assert quotation_excel_filename("SLQ-1/unsafe", 2) == "SLQ-1_unsafe-V2.xlsx"

from datetime import date
from io import BytesIO

from openpyxl import load_workbook

from app.models.customer import Customer
from app.services.customer_export_service import ARCHIVE_HEADERS, build_customer_archive_export


def test_customer_archive_export_is_a_real_safe_xlsx() -> None:
    customer = Customer(
        company_name="Example School",
        contact_name="Amy",
        customer_acquired_at=date(2026, 8, 12),
        whatsapp="00123456789",
        phone="01234567890",
        notes="=This must remain text in Excel",
    )

    workbook = load_workbook(BytesIO(build_customer_archive_export([customer])))
    worksheet = workbook["客户档案表"]

    assert tuple(cell.value for cell in worksheet[1]) == ARCHIVE_HEADERS
    assert worksheet.auto_filter.ref == "A1:AB1"
    assert worksheet["A2"].value == "Amy"
    assert worksheet["D2"].value.date() == date(2026, 8, 12)
    assert worksheet["F2"].value == "00123456789"
    assert worksheet["F2"].number_format == "@"
    assert worksheet["H2"].value == "01234567890"
    assert worksheet["H2"].number_format == "@"
    assert worksheet["T2"].value == "'=This must remain text in Excel"

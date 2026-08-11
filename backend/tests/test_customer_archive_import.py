from datetime import date

from openpyxl import Workbook

from scripts.import_customer_archive import EXPECTED_HEADERS, select_unique_records, workbook_records


def test_customer_archive_preflight_preserves_text_and_exact_duplicates(tmp_path):
    workbook_path = tmp_path / "客户档案.xlsx"
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "客户档案表"
    worksheet.append(EXPECTED_HEADERS)
    first = [date(2026, 3, 1), "询盘", "Amy", "Example Co", None, " first ", "USA", "实体店", "家具", "001234", "amy@example.com", None, 2, 3, 5, "已报价", None, date(2026, 3, 2), "是", "否"]
    latest = [date(2026, 3, 3), "询盘", "Amy", "Example Co", None, " latest ", "USA", "实体店", "家具", "001234", "amy@example.com", None, 2, 3, 5, "已报价", None, date(2026, 3, 4), "是", "否"]
    separate = [20260305, "RFQ", "Bob", "Second Co", "CEO", None, "China", "幼儿园", "蒙氏", None, None, 13000000000, 1, 1, 2, "新开发未回复", None, None, "否", "⚠需要跟进"]
    worksheet.append(first)
    worksheet.append(latest)
    worksheet.append(separate)
    workbook.save(workbook_path)

    records, report = workbook_records(workbook_path)
    selected, duplicates = select_unique_records(records)

    assert report["field_count"] == 20
    assert report["valid_customers"] == 3
    assert len(selected) == 2
    assert len(duplicates) == 1
    assert selected[0].row_number == 3
    assert selected[0].values["备注"] == "latest"
    assert selected[1].values["电话"] == "13000000000"
    assert selected[1].values["获得客户时间"] == date(2026, 3, 5)

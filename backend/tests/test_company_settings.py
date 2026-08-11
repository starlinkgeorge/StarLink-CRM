from app.config import get_settings


def test_company_contact_defaults_keep_quotation_exports_customer_ready(monkeypatch) -> None:
    """Optional deployment variables must not produce placeholder PDF contact data."""
    for name in (
        "COMPANY_NAME",
        "COMPANY_ALIBABA_STORE",
        "COMPANY_WEBSITE",
        "COMPANY_EMAIL",
        "COMPANY_WHATSAPP",
    ):
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()

    try:
        settings = get_settings()
        assert settings["company_name"] == "Dalian StarLink International Trade Co., Ltd."
        assert settings["company_alibaba_store"] == "https://starlinkforkids.en.alibaba.com"
        assert settings["company_website"] == "https://dlstarlink.com"
        assert settings["company_email"] == "starlink_george@foxmail.com"
        assert settings["company_whatsapp"] == "+86 17640412406"
    finally:
        get_settings.cache_clear()

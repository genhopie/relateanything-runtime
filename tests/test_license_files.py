from pathlib import Path


def test_notice_and_third_party_files_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    assert (root / "LICENSE").is_file()
    assert (root / "NOTICE").is_file()
    assert (root / "THIRD_PARTY_NOTICES.md").is_file()
    text = (root / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert "5d281bf0d89f2bbfd72ff5a14f9a40ce12534e790b0402e2ca970539c7bcc294" in text
    assert "5548f844c928c4b6f411fa8cbcc2bfa8dbbba437cb1d513975519f93c2a9ed21" in text

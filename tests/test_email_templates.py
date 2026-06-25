import email_templates as et


FAKE = {
    "bo_sung": ("[{{ma_project}}] {{ten_project}} — Cần bổ sung",
                "Chào {{ten_nguoi_gui}},\n\n{{noi_dung}}\n\nKết."),
    "footer": ("", "—\nMerch Agent · AMC Team · VNGGames"),
}

FIELDS = {
    "Mã project": "MERCH-021", "Tên project": "Áo PUBG", "Game": "PUBG",
    "Created by": {"name": "Vinh"}, "Deadline phê duyệt": "2026-07-01",
    "Deadline cần hàng": "2026-09-30", "Lý do cần PIC": "Quá 3 vòng",
    "Cảnh báo deadline": "⚠️ Deadline gấp",
}


def _patch(monkeypatch, mapping):
    monkeypatch.setattr(et, "_fetch_templates", lambda: mapping)


def test_substitutes_known_vars(monkeypatch):
    _patch(monkeypatch, FAKE)
    subject, body = et.render_email("bo_sung", FIELDS, core="Thiếu budget")
    assert subject == "[MERCH-021] Áo PUBG — Cần bổ sung"
    assert "Chào Vinh," in body
    assert "Thiếu budget" in body


def test_unknown_var_preserved(monkeypatch):
    _patch(monkeypatch, {"x": ("S", "{{khong_ton_tai}} end"), "footer": ("", "F")})
    _, body = et.render_email("x", FIELDS)
    assert "{{khong_ton_tai}}" in body


def test_footer_appended(monkeypatch):
    _patch(monkeypatch, FAKE)
    _, body = et.render_email("bo_sung", FIELDS, core="abc")
    assert body.rstrip().endswith("Merch Agent · AMC Team · VNGGames")


def test_missing_kind_uses_default(monkeypatch, caplog):
    _patch(monkeypatch, {"footer": ("", "F")})  # thiếu 'pic'
    import logging
    with caplog.at_level(logging.WARNING):
        subject, body = et.render_email("pic", FIELDS, core=None)
    assert subject  # fallback default, không rỗng
    assert "Quá 3 vòng" in body  # {{ly_do}} từ DEFAULT_TEMPLATES['pic']
    assert any("pic" in r.message for r in caplog.records)


def test_core_none_empty(monkeypatch):
    _patch(monkeypatch, FAKE)
    _, body = et.render_email("bo_sung", FIELDS, core=None)
    assert "{{noi_dung}}" not in body  # đã thay bằng rỗng


def test_creator_name_fallback(monkeypatch):
    _patch(monkeypatch, FAKE)
    fields = dict(FIELDS); fields["Created by"] = None
    _, body = et.render_email("bo_sung", fields, core="x")
    assert "Chào Anh/Chị," in body

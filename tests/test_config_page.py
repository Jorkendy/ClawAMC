from fastapi.testclient import TestClient

import main

client = TestClient(main.app)

# Trang /config la trang ADMIN/dev -> CHU DONG hien ten env var (khac /proposal, /guide).
# Test chot: cac bien nguong + so mac dinh (tu config) phai render dung.
REQUIRED = [
    'Cấu hình', 'Hạn DUYỆT', 'Merch PIC',
    'MAX_PROPOSAL_ROUNDS', 'MAX_CLARIFY_ROUNDS', 'MAX_SUPPLEMENT_ROUNDS',
    'MAX_BRIEF_ROUNDS', 'PROPOSAL_APPROVAL_DAYS',
    f'>{main.MAX_PROPOSAL_ROUNDS}<',      # so mac dinh render trong o bang
    f'+ {main.PROPOSAL_APPROVAL_DAYS} ngày',  # han duyet = gui + N
]

FORBIDDEN = [
    '{{',  # moi placeholder phai duoc thay
    'fld',  # field id Airtable
]


def test_config_route_ok():
    r = client.get("/config")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_config_has_required_content():
    html = client.get("/config").text
    missing = [s for s in REQUIRED if s not in html]
    assert not missing, f"Thiếu trong /config: {missing}"


def test_config_no_leftover_placeholder():
    html = client.get("/config").text
    leaked = [s for s in FORBIDDEN if s in html]
    assert not leaked, f"Lọt vào /config: {leaked}"


def test_rules_route_removed():
    """/rules da bi thay bang /proposal + /config."""
    assert client.get("/rules").status_code == 404

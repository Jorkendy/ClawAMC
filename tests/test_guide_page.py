from fastapi.testclient import TestClient

import main

client = TestClient(main.app)

# Trang /guide là tài liệu cho người dùng cuối (non-tech) — KHÔNG chứa chi tiết kỹ thuật
# (tên env var, mã email nội bộ, tên field Airtable). Test chốt khung + nội dung user-facing.
REQUIRED = [
    # anchors mục lục (7 mục)
    'id="buoc1"', 'id="buoc2"', 'id="buoc3"', 'id="buoc4"', 'id="buoc5"',
    'id="theo-doi"', 'id="faq"',
    # tiêu đề 5 bước
    'Bước 1', 'Bước 2', 'Bước 3', 'Bước 4', 'Bước 5',
    # hành động user-facing chính
    'gửi form', 'Duyệt', 'Cần sửa', 'đội Merch', 'brief',
]

# Chi tiết kỹ thuật KHÔNG được lọt vào trang hướng dẫn end-user.
FORBIDDEN = [
    'MAX_CLARIFY_ROUNDS', 'MAX_PROPOSAL_ROUNDS', 'MAX_BRIEF_ROUNDS',
    'PROPOSAL_APPROVAL_DAYS', 'bo_sung', 'handoff_design', 'qua_han',
    'Gửi phản hồi', 'Duyệt proposal?', 'Brief tự upload', '?id=',
]


def test_guide_route_ok():
    r = client.get("/guide")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_guide_has_required_content():
    html = client.get("/guide").text
    missing = [s for s in REQUIRED if s not in html]
    assert not missing, f"Thiếu trong /guide: {missing}"


def test_guide_no_technical_jargon():
    html = client.get("/guide").text
    leaked = [s for s in FORBIDDEN if s in html]
    assert not leaked, f"Lọt chi tiết kỹ thuật vào /guide: {leaked}"


DOC_ROUTES = ("/guide", "/flowchart", "/rules", "/email-guide")


def test_shared_nav_on_all_doc_pages():
    """Moi trang doc (sau khi serve) deu co thanh nav chung tro toi ca 4 trang."""
    for path in DOC_ROUTES:
        html = client.get(path).text
        for link in DOC_ROUTES:
            assert f'href="{link}"' in html, f"{path} thiếu nav → {link}"

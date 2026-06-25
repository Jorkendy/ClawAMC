from fastapi.testclient import TestClient

import main

client = TestClient(main.app)

# Mọi giá trị dưới đây phải xuất hiện trong trang /guide — chống bịa/sót.
REQUIRED = [
    # anchors mục lục (7 mục)
    'id="buoc1"', 'id="buoc2"', 'id="buoc3"', 'id="buoc4"', 'id="buoc5"',
    'id="theo-doi"', 'id="faq"',
    # link chéo đầu trang
    'href="/flowchart"', 'href="/rules"', 'href="/email-guide"',
    # routes nhắc trong nội dung
    '/proposal/',
    # email kinds
    'clarify', 'bo_sung', 'proposal', 'qua_han', 'plan', 'brief',
    'handoff_design', 'pic',
    # statuses
    'Chờ làm rõ yêu cầu', 'Chờ điều chỉnh', 'Chờ duyệt items',
    'Đã duyệt items', 'Chờ duyệt brief', 'Chờ thiết kế',
    'Chờ Merch PIC', 'Cần PIC xử lý',
    # field người bấm
    'Gửi phản hồi', 'Duyệt proposal?', 'Feedback proposal',
    'Bắt đầu design', 'Duyệt brief?', 'Feedback brief', 'Brief tự upload',
    # ngưỡng
    'MAX_CLARIFY_ROUNDS', 'MAX_PROPOSAL_ROUNDS', 'MAX_BRIEF_ROUNDS',
    'PROPOSAL_APPROVAL_DAYS',
]


def test_guide_route_ok():
    r = client.get("/guide")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_guide_has_required_content():
    html = client.get("/guide").text
    missing = [s for s in REQUIRED if s not in html]
    assert not missing, f"Thiếu trong /guide: {missing}"

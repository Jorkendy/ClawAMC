from fastapi.testclient import TestClient

import main

client = TestClient(main.app)

# Trang /proposal: minh bach cach tao proposal cho requester + leader (non-tech).
# Cac so nguong/gia dinh chen tu config -> luoi nay chong bia/sot: doi so trong config
# ma quen cap nhat trang -> test bat. Cung dam bao khong lo chi tiet ky thuat.
REQUIRED = [
    # khung & khai niem
    'Infinity Nikki', 'Relevance', 'Feasibility',
    'Ngày cần (lịch)',  # cong thuc deadline
    # nhan do tin cay
    '✅', '🟡',
    # so deadline (tu config: round((27+8+25)*1.4)=84, round((27+8+18)*1.4)=74)
    '~84', '~74',
    # overhead breakdown (Chuan bi 18 + Duyet mau 7 + Giao hang 2)
    'Chuẩn bị 18', 'Duyệt mẫu 7', 'Giao hàng 2',
    '1.4',  # he so quy doi
    # phan khuc gia (mirror value_tier)
    '100.000', '500.000',
    # 3 kich ban pipeline (min/avg/max = 31/53/68)
    'Nhanh nhất 31', 'Trung bình 53', 'Chậm nhất 68',
    # vi du cu the
    '300.000đ/bộ', '150.000.000đ', 'Figure', '1.000',
    # 3 ket cuc deadline
    'ĐỦ', 'GẤP', 'KHÔNG ĐỦ',
]

# Trang huong toi non-tech + leader -> KHONG lo chi tiet ky thuat / placeholder chua thay.
FORBIDDEN = [
    '{{',  # moi placeholder phai duoc thay bang so that tu config
    'config.py', 'fld',  # ten file / field id Airtable
    'DEADLINE_OVERHEAD', 'WORKDAYS_TO_CALENDAR', 'CREATIVE_LEADTIME',
    'MIN_FAST_ITEMS', 'DEADLINE_BUFFER', 'PIPELINE_WORKDAYS',
    'value_tier', 'deadline_days_needed',  # ten ham
    'Người đặt',  # dung "Requester", khong dich
    'bạn', 'Bạn',  # giong trung lap, khong xung "ban"
]


def test_proposal_route_ok():
    r = client.get("/proposal")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_proposal_has_required_content():
    html = client.get("/proposal").text
    missing = [s for s in REQUIRED if s not in html]
    assert not missing, f"Thiếu trong /proposal: {missing}"


def test_proposal_no_technical_jargon():
    html = client.get("/proposal").text
    leaked = [s for s in FORBIDDEN if s in html]
    assert not leaked, f"Lọt chi tiết kỹ thuật vào /proposal: {leaked}"

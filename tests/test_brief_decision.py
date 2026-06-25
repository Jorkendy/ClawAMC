import pipeline


def test_action_upload_priority():
    f = {"Brief tự upload": [{"url": "x"}], "Duyệt brief?": "Duyệt"}
    assert pipeline._brief_action(f) == "upload"


def test_action_approve():
    assert pipeline._brief_action({"Duyệt brief?": "Duyệt"}) == "approve"


def test_action_revise():
    assert pipeline._brief_action({"Duyệt brief?": "Cần sửa", "Feedback brief": "đổi màu"}) == "revise"


def test_action_revise_no_feedback_ignored():
    assert pipeline._brief_action({"Duyệt brief?": "Cần sửa"}) == "ignore"


def test_action_ignore():
    assert pipeline._brief_action({}) == "ignore"

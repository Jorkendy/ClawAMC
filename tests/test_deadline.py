from proposal import catalogue_floor_days

def _cat(lm, sx):
    return {"Thời gian lên mẫu": lm, "Thời gian sản xuất": sx}

def test_floor_picks_fastest_item():
    by_name = {
        "Móc khóa": _cat("5", "10"),      # (27+5+10)*1.4 = 58.8 -> 59
        "Gấu bông": _cat("15", "60"),     # (27+15+60)*1.4 = 142.8 -> 143
    }
    days, name = catalogue_floor_days(by_name)
    assert name == "Móc khóa"
    assert days == 59

def test_floor_empty_catalogue():
    assert catalogue_floor_days({}) == (0, "")

def test_floor_uses_fallback_when_leadtime_missing():
    # thieu lead-time -> fallback 8/18 -> (27+8+18)*1.4 = 74.2 -> 74
    days, name = catalogue_floor_days({"X": {}})
    assert days == 74 and name == "X"

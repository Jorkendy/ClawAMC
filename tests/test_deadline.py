from proposal import catalogue_floor_days, _fit_within_deadline

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

def test_split_drops_slowest_until_fits():
    by_name = {
        "Móc khóa": _cat("5", "10"),    # lead 15 -> need (27+5+10)*1.4=59
        "Áo thun":  _cat("8", "20"),    # lead 28 -> need 77
    }
    items = [
        {"ten": "Móc khóa", "nguon": "catalogue"},
        {"ten": "Áo thun",  "nguon": "catalogue"},
        {"ten": "Khăn lụa", "nguon": "creative"}, # creative lead 8/25 -> need (27+8+25)*1.4=84
    ]
    # days_left=60: chi Móc khóa kip (59<=60); Áo thun(77) & creative(84) bi bo
    fast, slow = _fit_within_deadline(items, by_name, 60)
    assert [it["ten"] for it in fast] == ["Móc khóa"]
    assert {it["ten"] for it in slow} == {"Áo thun", "Khăn lụa"}

def test_split_all_fit():
    by_name = {"Móc khóa": _cat("5", "10")}
    items = [{"ten": "Móc khóa", "nguon": "catalogue"}]
    fast, slow = _fit_within_deadline(items, by_name, 200)
    assert len(fast) == 1 and slow == []

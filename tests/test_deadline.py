from datetime import date, timedelta
from proposal import catalogue_floor_days, _fit_within_deadline, _resolve_deadline
import config

def _cat(lm, sx):
    return {"Thời gian lên mẫu": lm, "Thời gian sản xuất": sx}

def _fields(days_from_today):
    d = date.today() + timedelta(days=days_from_today)
    return {"Deadline cần hàng": d.isoformat()}

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

# Tests for _resolve_deadline
CAT = {
    "Móc khóa": _cat("5", "10"),   # need 59
    "Áo thun":  _cat("8", "20"),   # need 77
    "Sticker":  _cat("4", "8"),    # need (27+4+8)*1.4=54.6->55
}

def test_ok_when_full_fits():
    items=[{"ten":"Áo thun","nguon":"catalogue"}]
    r=_resolve_deadline({"items":items}, _fields(200), CAT, "X")
    assert r["kind"]=="ok" and r["warn"]==""

def test_ok_sat_warning():
    items=[{"ten":"Áo thun","nguon":"catalogue"}]  # need 77
    r=_resolve_deadline({"items":items}, _fields(80), CAT, "X")  # 77<=80<77*1.15=88.5
    assert r["kind"]=="ok" and "sát" in r["warn"]

def test_fast_when_subset_fits(monkeypatch):
    monkeypatch.setattr(config,"MIN_FAST_ITEMS",2)
    # must also patch the reference already imported in proposal
    import proposal; monkeypatch.setattr(proposal,"MIN_FAST_ITEMS",2)
    items=[{"ten":"Móc khóa","nguon":"catalogue"},
           {"ten":"Sticker","nguon":"catalogue"},
           {"ten":"Áo thun","nguon":"catalogue"}]  # full need 77
    r=_resolve_deadline({"items":items}, _fields(60), CAT, "X")  # Móc(59)+Sticker(55) fit, Áo(77) dropped
    assert r["kind"]=="fast"
    assert {i["ten"] for i in r["fast"]}=={"Móc khóa","Sticker"}
    assert {i["ten"] for i in r["slow"]}=={"Áo thun"}

def test_adjust_when_fast_too_thin():
    items=[{"ten":"Áo thun","nguon":"catalogue"}]  # need 77, fast empty when days<77
    r=_resolve_deadline({"items":items}, _fields(40), CAT, "X")
    assert r["kind"]=="adjust"
    assert r["floor"]==55 and r["floor_name"]=="Sticker"  # fastest item in catalogue

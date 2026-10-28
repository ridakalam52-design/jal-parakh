import re


def test_strip_chart_endpoint(client):
    r = client.get("/api/strip-chart")
    assert r.status_code == 200
    data = r.json()
    assert data["standard"] == "BIS IS 10500:2012"
    assert "chart_note" in data and data["chart_note"].startswith("Reference chart used by the synthetic demo strips")
    params = {p["param"]: p for p in data["params"]}
    # All STRIP_PARAMS should be present
    from app.standards import STRIP_PARAMS
    for k in STRIP_PARAMS:
        assert k in params
        p = params[k]
        assert "name_en" in p and "name_hi" in p
        assert "unit" in p and "limit_text" in p
        # swatches may be None for some params
        if p["swatches"] is not None:
            # should be a list of {value, hex} dicts
            assert isinstance(p["swatches"], list)
            hexre = re.compile(r"^#[0-9a-f]{6}$")
            last_v = None
            for s in p["swatches"]:
                assert isinstance(s, dict)
                assert "value" in s and "hex" in s
                v = s["value"]
                hx = s["hex"]
                assert isinstance(v, (int, float))
                assert isinstance(hx, str)
                assert hexre.match(hx)
                if last_v is not None:
                    assert v > last_v, f"swatches for {k} not strictly increasing: {last_v} !< {v}"
                last_v = v
        else:
            assert p["swatches"] is None

    # Fluoride checks
    f = params["fluoride"]
    assert f["acceptable"] == 1.0
    assert f["permissible"] == 1.5
    assert f["health"] is True
    assert f["source_short"] == "BIS"

    # Nitrite should be WHO
    n = params["nitrite"]
    assert n["source_short"] == "WHO"

    # Arsenic should have no swatches (not present in STRIP_CHARTS)
    a = params["arsenic"]
    assert a["swatches"] is None


def test_script_chart_rows():
    # Import the script module to get CHART and compare row labels
    import importlib
    m = importlib.import_module("scripts.make_demo_strips")
    labels = [r[0] for r in m.CHART]
    expected = ["pH", "Hardness", "Alkalinity", "Nitrate", "Nitrite", "Free Cl", "Iron", "Fluoride", "Lead"]
    assert labels == expected, f"CHART labels differ: {labels}"


def test_script_chart_matches_original_ramps():
    """Moving the ramps into app/strip_chart.py must not change the demo images: same rows, values and colours."""
    import importlib
    m = importlib.import_module("scripts.make_demo_strips")
    expected_first_last = {
        "pH": ((6.0, (236, 160, 60)), (8.5, (70, 120, 130))),
        "Hardness": ((0, (60, 90, 170)), (1000, (210, 60, 100))),
        "Fluoride": ((0, (240, 120, 150)), (4, (215, 225, 225))),
        "Lead": ((0, (250, 250, 245)), (1, (150, 120, 185))),
    }
    rows = {label: ramp for label, _unit, ramp in m.CHART}
    assert all(len(r) == 6 for r in rows.values())
    for label, (first, last) in expected_first_last.items():
        assert rows[label][0] == first and rows[label][-1] == last


def test_strip_chart_hex_conversion():
    from app import strip_chart
    assert strip_chart.rgb_tuple_to_hex((236, 160, 60)) == "#eca03c"
    assert strip_chart.get_swatches_hex_by_param("ph")[0] == {"value": 6.0, "hex": "#eca03c"}
    assert strip_chart.get_swatches_hex_by_param("copper") is None

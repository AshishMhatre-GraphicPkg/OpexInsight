from src import actions


def setup_function(_):
    actions.reset_unmapped_counter()


def test_exact_match_downtime_reason_code():
    g = actions.lookup_action("0002-Paperboard", "Downtime Reason")
    assert g.is_generic is False
    assert g.category == "Material & Board Defect"
    assert "board" in g.action.lower()


def test_case_insensitive_match():
    g_lower = actions.lookup_action("0002-paperboard", "Downtime Reason")
    g_exact = actions.lookup_action("0002-Paperboard", "Downtime Reason")
    assert g_lower.action == g_exact.action
    assert g_lower.is_generic is False


def test_kpi_lever_uses_fallback_key_when_no_reason():
    g = actions.lookup_action(None, "Speed")
    assert g.is_generic is False
    assert "speed" in g.action.lower()


def test_unmapped_reason_falls_back_to_generic():
    g = actions.lookup_action("Totally Made Up Reason Text", "Downtime Reason")
    assert g.is_generic is True
    assert g.action == actions._GENERIC_ACTION


def test_sentinel_row_falls_back_to_generic():
    # The literal '-' row in the lookup carries the "not yet mapped" sentinel text.
    g = actions.lookup_action("-", "Downtime Reason")
    assert g.is_generic is True
    assert g.action == actions._GENERIC_ACTION
    assert not g.action.startswith(actions._SENTINEL_PREFIX)


def test_blank_key_falls_back_to_generic():
    g = actions.lookup_action(None, "")
    assert g.is_generic is True


def test_lookup_loads_full_reason_universe():
    table = actions.load_action_lookup()
    # 1999 Time Reason strings + 7 KPI levers + '-' fallback, minus any dup keys
    assert len(table) > 1900


def test_unmapped_counter_tracks_generic_fallbacks():
    actions.reset_unmapped_counter()
    actions.lookup_action("0002-Paperboard", "Downtime Reason")  # real hit
    actions.lookup_action("Nonexistent Reason", "Downtime Reason")  # miss
    assert actions._lookup_count == 2
    assert actions._unmapped_count == 1

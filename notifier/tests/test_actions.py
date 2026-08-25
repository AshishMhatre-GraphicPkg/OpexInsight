from src import actions


def setup_function(_):
    actions.reset_unmapped_counter()


def test_real_lever_department_hit_returns_three_pairs():
    g = actions.lookup_action("Speed", "Sheetfed Printing")
    assert g.is_generic is False
    assert g.category == "Mechanical Breakdown"
    assert len(g.pairs) == 3
    assert "board curl" in g.pairs[0].factor.lower()
    assert g.action == g.pairs[0].action


def test_case_insensitive_match_on_lever_and_department():
    g_lower = actions.lookup_action("speed", "sheetfed printing")
    g_exact = actions.lookup_action("Speed", "Sheetfed Printing")
    assert g_lower.action == g_exact.action
    assert g_lower.is_generic is False


def test_downtime_reason_sublever_resolves_via_parent_outcome():
    # A Downtime Reason sub-lever has no row of its own in the lookup — it
    # resolves via Lever_N_Parent_Outcome ("Downtime %") instead, whose row
    # carries a single generic-review action with a blank factor.
    g = actions.lookup_action("Downtime Reason", "Sheetfed Printing", parent_outcome="Downtime %")
    assert g.is_generic is False
    assert g.category == "Outcome (Roll-Up KPI)"
    assert len(g.pairs) == 1
    assert g.pairs[0].factor == ""
    assert "root cause" in g.pairs[0].action.lower()


def test_downtime_reason_sublever_defaults_parent_when_missing():
    g = actions.lookup_action("Downtime Reason", "Sheetfed Printing", parent_outcome=None)
    assert g.is_generic is False
    assert g.category == "Outcome (Roll-Up KPI)"


def test_department_miss_falls_back_to_generic():
    # Speed exists for Sheetfed Printing but not for Gluer — strict match,
    # no cross-department fallback.
    g = actions.lookup_action("Speed", "Gluer")
    assert g.is_generic is True
    assert g.action == actions._GENERIC_ACTION
    assert g.pairs == []


def test_unmapped_lever_falls_back_to_generic():
    g = actions.lookup_action("Totally Made Up Lever", "Sheetfed Printing")
    assert g.is_generic is True
    assert g.action == actions._GENERIC_ACTION


def test_blank_key_falls_back_to_generic():
    g = actions.lookup_action("", "")
    assert g.is_generic is True


def test_lookup_loads_eight_sheetfed_rows():
    table = actions.load_action_lookup()
    assert len(table) == 8
    assert all(dept == "sheetfed printing" for dept, _lever in table)


def test_blank_pairs_are_pruned_but_action_only_pairs_kept():
    table = actions.load_action_lookup()
    _category, pairs = table[("sheetfed printing", "downtime %")]
    # Downtime % only has Typical Actions 1 populated — the other two pairs
    # (both factor and action blank) must be dropped, not rendered as empty.
    assert len(pairs) == 1


def test_unmapped_counter_tracks_generic_fallbacks():
    actions.reset_unmapped_counter()
    actions.lookup_action("Speed", "Sheetfed Printing")  # real hit
    actions.lookup_action("Speed", "Gluer")  # department miss
    assert actions._lookup_count == 2
    assert actions._unmapped_count == 1

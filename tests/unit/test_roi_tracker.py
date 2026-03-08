"""Tests unitarios para utils/roi_tracker.py."""

from types import SimpleNamespace

from utils.roi_tracker import ROITracker, init_roi_tracker, quick_track


class SessionState(dict):
    """Doble simple de st.session_state con acceso atributo y dict."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value

    def __delattr__(self, name):
        try:
            del self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


def test_init_session_creates_roi_data():
    session_state = SessionState()

    tracker = ROITracker(session_state)

    assert tracker.session_state.roi_data["total_hrs_saved"] == 0.0
    assert tracker.session_state.roi_data["total_value"] == 0.0
    assert tracker.session_state.roi_data["actions"] == []


def test_get_user_hourly_rate_uses_user_role_value():
    session_state = SessionState()
    session_state.user = SimpleNamespace(role=SimpleNamespace(value="cfo"))
    tracker = ROITracker(session_state)

    assert tracker.get_user_hourly_rate() == 3000


def test_get_user_hourly_rate_falls_back_to_default_user_rate():
    session_state = SessionState()
    tracker = ROITracker(session_state)

    assert tracker.get_user_hourly_rate() == 500


def test_track_action_uses_benchmark_and_updates_totals():
    session_state = SessionState()
    tracker = ROITracker(session_state)

    result = tracker.track_action("assistant", "nl2sql_query", quantity=2)

    assert result["hrs_saved"] == 1.0
    assert result["value"] == 500.0
    assert tracker.session_state.roi_data["total_hrs_saved"] == 1.0
    assert tracker.session_state.roi_data["total_value"] == 500.0
    assert tracker.session_state.roi_data["today"]["actions_count"] == 1
    assert tracker.session_state.roi_data["actions"][-1]["action"] == "nl2sql_query"


def test_track_action_allows_custom_hours_override():
    session_state = SessionState()
    tracker = ROITracker(session_state)

    result = tracker.track_action("exec", "generate_exec_report", custom_hrs_saved=3.25)

    assert result["hrs_saved"] == 3.25
    assert result["value"] == 1625.0


def test_track_risk_avoided_adds_value_and_category():
    session_state = SessionState()
    tracker = ROITracker(session_state)

    result = tracker.track_risk_avoided("cxc", "morosidad", 125000, "cliente crítico")

    assert result["value"] == 125000
    assert tracker.session_state.roi_data["total_value"] == 125000
    assert tracker.session_state.roi_data["actions"][-1]["category"] == "risk_avoided"
    assert tracker.session_state.roi_data["today"]["value"] == 125000


def test_set_analyst_salary_enforces_minimum():
    session_state = SessionState()
    tracker = ROITracker(session_state)

    tracker.set_analyst_salary(100)

    assert tracker.get_analyst_salary() == 1000


def test_calculate_analyst_cost_equivalent_returns_expected_fields():
    session_state = SessionState()
    tracker = ROITracker(session_state)
    tracker.set_analyst_salary(30000)

    result = tracker.calculate_analyst_cost_equivalent(44)

    assert result["workdays"] == 5.5
    assert result["months_analyst"] == 0.25
    assert result["monthly_savings"] == 13200
    assert result["analyst_salary"] == 30000
    assert "0.25" in result["justification"]


def test_get_summary_aggregates_tracked_actions():
    session_state = SessionState()
    tracker = ROITracker(session_state)
    tracker.track_action("assistant", "nl2sql_query", quantity=1)
    tracker.track_action("assistant", "nl2sql_chart", quantity=2)

    summary = tracker.get_summary()

    assert summary["today"]["hrs"] == 1.0
    assert summary["total"]["actions"] == 2
    assert summary["total"]["value"] == 500.0
    assert summary["today"]["analyst_equiv"]["monthly_savings"] == 300.0


def test_get_recent_actions_limits_to_last_items():
    session_state = SessionState()
    tracker = ROITracker(session_state)
    tracker.track_action("m", "nl2sql_query")
    tracker.track_action("m", "nl2sql_chart")
    tracker.track_action("m", "nl2sql_export")

    recent = tracker.get_recent_actions(limit=2)

    assert len(recent) == 2
    assert [item["action"] for item in recent] == ["nl2sql_chart", "nl2sql_export"]


def test_reset_session_clears_accumulated_values():
    session_state = SessionState()
    tracker = ROITracker(session_state)
    tracker.track_action("assistant", "nl2sql_query", quantity=3)

    tracker.reset_session()

    assert tracker.session_state.roi_data["total_hrs_saved"] == 0.0
    assert tracker.session_state.roi_data["total_value"] == 0.0
    assert tracker.session_state.roi_data["actions"] == []


def test_init_roi_tracker_reuses_existing_instance():
    session_state = SessionState()

    tracker1 = init_roi_tracker(session_state)
    tracker2 = init_roi_tracker(session_state)

    assert tracker1 is tracker2


def test_quick_track_uses_helper_and_returns_tracking_result():
    session_state = SessionState()

    result = quick_track(session_state, "assistant", "nl2sql_export", quantity=2)

    assert result["hrs_saved"] == 0.3
    assert result["value"] == 150.0
    assert session_state.roi_tracker.session_state is session_state
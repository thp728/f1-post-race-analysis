"""Tests for src/circuit.py — cluster lookups and normalization."""

from src.circuit import (
    CircuitCluster,
    get_circuits_in_cluster,
    get_cluster,
    normalize_circuit_id,
)


class TestGetCluster:
    def test_monza_is_straight_line(self):
        assert get_cluster("monza") == CircuitCluster.STRAIGHT_LINE_DOMINANT

    def test_silverstone_is_classic(self):
        assert get_cluster("silverstone") == CircuitCluster.CLASSIC_HIGH_SPEED

    def test_monaco_is_tight(self):
        assert get_cluster("monaco") == CircuitCluster.TIGHT_LOW_OVERTAKING

    def test_bahrain_is_night_desert(self):
        assert get_cluster("bahrain") == CircuitCluster.NIGHT_DESERT

    def test_baku_is_fast_street(self):
        assert get_cluster("baku") == CircuitCluster.FAST_STREET

    def test_unknown_returns_none(self):
        assert get_cluster("nonexistent_circuit") is None

    def test_case_insensitive(self):
        assert get_cluster("MONZA") == CircuitCluster.STRAIGHT_LINE_DOMINANT


class TestGetCircuitsInCluster:
    def test_night_desert_has_bahrain(self):
        circuits = get_circuits_in_cluster(CircuitCluster.NIGHT_DESERT)
        assert "bahrain" in circuits

    def test_returns_list(self):
        result = get_circuits_in_cluster(CircuitCluster.CLASSIC_HIGH_SPEED)
        assert isinstance(result, list)
        assert len(result) > 0


class TestNormalizeCircuitId:
    def test_bahrain_gp(self):
        assert normalize_circuit_id("Bahrain Grand Prix") == "bahrain"

    def test_british_gp(self):
        assert normalize_circuit_id("British Grand Prix") == "silverstone"

    def test_italian_gp(self):
        assert normalize_circuit_id("Italian Grand Prix") == "monza"

    def test_case_insensitive(self):
        assert normalize_circuit_id("BAHRAIN GRAND PRIX") == "bahrain"

    def test_unknown_event_slugified(self):
        result = normalize_circuit_id("Some New Grand Prix")
        assert " " not in result

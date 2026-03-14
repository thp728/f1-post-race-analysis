"""Circuit classification and cluster mapping."""

from enum import Enum
from typing import List, Optional


class CircuitCluster(Enum):
    """Five circuit type clusters based on track characteristics."""
    NIGHT_DESERT = "night_desert"
    FAST_STREET = "fast_street"
    TIGHT_LOW_OVERTAKING = "tight_low_overtaking"
    CLASSIC_HIGH_SPEED = "classic_high_speed"
    STRAIGHT_LINE_DOMINANT = "straight_line_dominant"


# Static mapping: normalized circuit key -> cluster
CIRCUIT_CLUSTERS: dict = {
    # Night/desert
    "bahrain": CircuitCluster.NIGHT_DESERT,
    "sakhir": CircuitCluster.NIGHT_DESERT,
    "lusail": CircuitCluster.NIGHT_DESERT,
    "qatar": CircuitCluster.NIGHT_DESERT,
    "yas_marina": CircuitCluster.NIGHT_DESERT,
    "abu_dhabi": CircuitCluster.NIGHT_DESERT,
    "las_vegas": CircuitCluster.NIGHT_DESERT,
    "jeddah": CircuitCluster.NIGHT_DESERT,
    "saudi_arabia": CircuitCluster.NIGHT_DESERT,

    # Fast street
    "baku": CircuitCluster.FAST_STREET,
    "azerbaijan": CircuitCluster.FAST_STREET,
    "miami": CircuitCluster.FAST_STREET,
    "marina_bay": CircuitCluster.FAST_STREET,
    "singapore": CircuitCluster.FAST_STREET,

    # Tight/low overtaking
    "monaco": CircuitCluster.TIGHT_LOW_OVERTAKING,
    "monte_carlo": CircuitCluster.TIGHT_LOW_OVERTAKING,
    "hungaroring": CircuitCluster.TIGHT_LOW_OVERTAKING,
    "budapest": CircuitCluster.TIGHT_LOW_OVERTAKING,
    "zandvoort": CircuitCluster.TIGHT_LOW_OVERTAKING,

    # Classic high-speed
    "silverstone": CircuitCluster.CLASSIC_HIGH_SPEED,
    "spa": CircuitCluster.CLASSIC_HIGH_SPEED,
    "spa-francorchamps": CircuitCluster.CLASSIC_HIGH_SPEED,
    "suzuka": CircuitCluster.CLASSIC_HIGH_SPEED,
    "japan": CircuitCluster.CLASSIC_HIGH_SPEED,
    "catalunya": CircuitCluster.CLASSIC_HIGH_SPEED,
    "barcelona": CircuitCluster.CLASSIC_HIGH_SPEED,
    "spain": CircuitCluster.CLASSIC_HIGH_SPEED,
    "cota": CircuitCluster.CLASSIC_HIGH_SPEED,
    "austin": CircuitCluster.CLASSIC_HIGH_SPEED,
    "united_states": CircuitCluster.CLASSIC_HIGH_SPEED,
    "imola": CircuitCluster.CLASSIC_HIGH_SPEED,
    "portimao": CircuitCluster.CLASSIC_HIGH_SPEED,
    "shanghai": CircuitCluster.CLASSIC_HIGH_SPEED,
    "china": CircuitCluster.CLASSIC_HIGH_SPEED,

    # Straight-line speed dominant
    "monza": CircuitCluster.STRAIGHT_LINE_DOMINANT,
    "italy": CircuitCluster.STRAIGHT_LINE_DOMINANT,
    "montreal": CircuitCluster.STRAIGHT_LINE_DOMINANT,
    "canada": CircuitCluster.STRAIGHT_LINE_DOMINANT,
    "red_bull_ring": CircuitCluster.STRAIGHT_LINE_DOMINANT,
    "spielberg": CircuitCluster.STRAIGHT_LINE_DOMINANT,
    "austria": CircuitCluster.STRAIGHT_LINE_DOMINANT,
    "mexico": CircuitCluster.STRAIGHT_LINE_DOMINANT,
    "mexico_city": CircuitCluster.STRAIGHT_LINE_DOMINANT,
    "albert_park": CircuitCluster.STRAIGHT_LINE_DOMINANT,
    "melbourne": CircuitCluster.STRAIGHT_LINE_DOMINANT,
    "australia": CircuitCluster.STRAIGHT_LINE_DOMINANT,
    "interlagos": CircuitCluster.STRAIGHT_LINE_DOMINANT,
    "sao_paulo": CircuitCluster.STRAIGHT_LINE_DOMINANT,
    "brazil": CircuitCluster.STRAIGHT_LINE_DOMINANT,
}

# Mapping from common FastF1 EventName patterns to normalized keys
_EVENT_NAME_MAP: dict = {
    "bahrain grand prix": "bahrain",
    "saudi arabian grand prix": "jeddah",
    "australian grand prix": "albert_park",
    "japanese grand prix": "suzuka",
    "chinese grand prix": "shanghai",
    "miami grand prix": "miami",
    "emilia romagna grand prix": "imola",
    "monaco grand prix": "monaco",
    "canadian grand prix": "montreal",
    "spanish grand prix": "catalunya",
    "austrian grand prix": "red_bull_ring",
    "british grand prix": "silverstone",
    "hungarian grand prix": "hungaroring",
    "belgian grand prix": "spa",
    "dutch grand prix": "zandvoort",
    "italian grand prix": "monza",
    "azerbaijan grand prix": "baku",
    "singapore grand prix": "marina_bay",
    "united states grand prix": "cota",
    "mexico city grand prix": "mexico_city",
    "são paulo grand prix": "interlagos",
    "sao paulo grand prix": "interlagos",
    "las vegas grand prix": "las_vegas",
    "qatar grand prix": "lusail",
    "abu dhabi grand prix": "yas_marina",
    "portuguese grand prix": "portimao",
}


def normalize_circuit_id(event_name: str) -> str:
    """Convert FastF1 event name to normalized circuit key.

    Examples:
        'Bahrain Grand Prix' -> 'bahrain'
        'British Grand Prix' -> 'silverstone'
    """
    lower = event_name.strip().lower()

    # Try exact match first
    if lower in _EVENT_NAME_MAP:
        return _EVENT_NAME_MAP[lower]

    # Try partial match
    for pattern, circuit_id in _EVENT_NAME_MAP.items():
        if pattern in lower or lower in pattern:
            return circuit_id

    # Fallback: slugify the event name
    return lower.replace(" grand prix", "").replace(" ", "_")


def get_cluster(circuit_id: str) -> Optional[CircuitCluster]:
    """Look up the cluster for a circuit."""
    return CIRCUIT_CLUSTERS.get(circuit_id.lower())


def get_circuits_in_cluster(cluster: CircuitCluster) -> List[str]:
    """Return all circuit IDs in a given cluster (deduplicated primary keys only)."""
    # Return only the primary/canonical circuit IDs to avoid duplicates
    seen = set()
    result = []
    for cid, c in CIRCUIT_CLUSTERS.items():
        if c == cluster and cid not in seen:
            seen.add(cid)
            result.append(cid)
    return result

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_textile_class_is_in_taxonomy_and_has_handling_advice() -> None:
    taxonomy = json.loads((ROOT / "backend" / "taxonomy.json").read_text(encoding="utf-8"))
    category = next(item for item in taxonomy["categories"] if item["id"] == "textile")
    assert taxonomy["version"] == "2026-11-13.2"
    assert category["detection_supported"] is True
    assert category["model_names"] == ["Textile"]
    assert category["training_readiness"] == "ready_for_training"
    knowledge = json.loads((ROOT / "backend" / "knowledge.json").read_text(encoding="utf-8"))
    advice = next(item for item in knowledge["materials"] if item["id"] == "textile")
    assert "áo khoác cũ" in advice["examples"]
    assert "thú nhồi bông" in advice["caution"]

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.data_loader import DataLoader
from backend.entity_resolver import EntityResolver
from backend.validator import IntentValidator
from backend.agent_understanding import QuestionUnderstandingAgent
from backend.pandas_engine import PandasAnalysisEngine
from backend.agent_chart_selector import ChartSelectionAgent
from backend.agent_insight import InsightAgent

def run_all_tests():
    print("=== 1. Testing DataLoader ===")
    loader = DataLoader.get_instance()
    print(f"Crops loaded ({len(loader.crops)}):", sorted(list(loader.crops))[:5])
    print(f"Mandis loaded ({len(loader.mandi_names)}):", sorted(list(loader.mandi_names))[:5])
    assert "Wheat" in loader.crops, "Wheat should be in crops"
    assert len(loader.mandi_names) > 0, "Mandis should be loaded"
    print("DataLoader PASSED!")

    print("\n=== 2. Testing EntityResolver (Typo tolerance) ===")
    resolver = EntityResolver.get_instance()
    crop, conf, _ = resolver.resolve_crop("wheet")
    print(f"Resolved 'wheet' -> '{crop}' (conf: {conf})")
    assert crop == "Wheat", f"Expected Wheat, got {crop}"

    crop, conf, _ = resolver.resolve_crop("kapas")
    print(f"Resolved 'kapas' -> '{crop}' (conf: {conf})")
    assert crop == "Cotton", f"Expected Cotton, got {crop}"

    mandi, mid, conf, _ = resolver.resolve_mandi("ludhiyana")
    print(f"Resolved 'ludhiyana' -> '{mandi}' (id: {mid})")
    assert mandi is not None and "ludhiana" in mandi.lower(), f"Expected Ludhiana, got {mandi}"
    print("EntityResolver PASSED!")

    print("\n=== 3. Testing QuestionUnderstandingAgent & Pipeline on Contract Bonus Queries ===")
    ua = QuestionUnderstandingAgent()
    val = IntentValidator()
    engine = PandasAnalysisEngine()
    chart_sel = ChartSelectionAgent()
    insight = InsightAgent()

    test_queries = [
        ("Which 5 mandis had the highest wheat arrivals?", "bar", "ranking"),
        ("Show wheat prices from January to September.", "line", "trend"),
        ("Did rainfall affect wheat arrivals?", "scatter", "cross_dataset_analysis"),
        ("Which mandi had highest wheet price?", "bar", "ranking"),
        ("Which mandis had high arrivals but low prices?", "bar", "cross_dataset_analysis"),
        ("What share of arrivals came from each crop?", "pie", "aggregation"),
        ("What was the average wheat price?", "kpi", "aggregation"),
        ("Predict wheat prices next year.", None, "unsupported"),
    ]

    for q, exp_chart, exp_intent in test_queries:
        print(f"\nTesting Query: '{q}'")
        intent = ua.understand(q)
        print(f"  -> Extracted Intent: {intent.get('intent')}")
        assert intent.get("intent") == exp_intent, f"Expected intent {exp_intent}, got {intent.get('intent')}"

        if exp_intent == "unsupported":
            print(f"  -> Successfully caught unsupported query: {intent.get('unsupported_reason')}")
            continue

        is_valid, validated_intent, err = val.validate(intent)
        assert is_valid, f"Validation failed: {err}"

        res = engine.execute(validated_intent)
        print(f"  -> Calculated records count: {len(res.get('records', []))}")
        assert "records" in res, "Engine result must contain records"

        chart = chart_sel.select_and_build_spec(validated_intent, res)
        if exp_chart:
            assert chart is not None, f"Expected chart {exp_chart}, got None"
            print(f"  -> Selected Chart: {chart.get('type')}")
            assert chart.get("type") == exp_chart, f"Expected chart {exp_chart}, got {chart.get('type')}"

        summary = insight.generate_summary_and_answer(validated_intent, res, chart)
        print(f"  -> AI Summary: {summary.get('summary')}")
        assert summary.get("summary"), "Summary must not be empty"

    print("\nALL CONTRACT PIPELINE TESTS PASSED!")

if __name__ == "__main__":
    run_all_tests()

"""Reproducible synthetic network benchmark; timing is reported, never a test gate."""

import argparse
import gc
import hashlib
import importlib
import json
from pathlib import Path
import time
import tracemalloc

from qgis.core import Qgis

from .test_scenarios_profiles_qgis import APP, layer
from ..core.multimodal_accessibility import MPYYMultimodalAccessibilityEngine


def measure(engine, count: int, demand_count: int) -> dict:
    graphs = [layer("LineString", [
        (f"LINESTRING({index} 0,{index + 1} 0)",
         ["WALK" if index % 2 == 0 else "TRANSIT", speed, "FT"])
        for index in range(count)
    ], "&field=mode:string&field=speed_kmh:double&field=direction:string")
        for speed in (60.0, 120.0)]
    demand = layer("Point", [("POINT(0 0)", []) for _ in range(demand_count)])
    facilities = layer("Point", [(f"POINT({count} 0)", [])])
    gc.collect()
    tracemalloc.start()
    start = time.perf_counter()
    results = [engine.analyze(
        graph.getFeatures(), demand.getFeatures(), facilities.getFeatures(), count,
        transfer_penalty_min=0.5, snap_tolerance_m=0.1,
    ) for graph in graphs]
    elapsed = time.perf_counter() - start
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    expected = count / 1000.0 + (count - 1) * 0.5
    assert results[0].accessible_count == demand_count
    assert results[1].accessible_count == demand_count
    assert abs(results[0].records[0].route_time_min - expected) < 1e-6
    assert abs(results[1].records[0].route_time_min - (expected - count / 2000.0)) < 1e-6
    signature = [{
        "status": row.status, "time": round(row.route_time_min, 6),
        "modes_sha256": hashlib.sha256(row.modes.encode()).hexdigest(),
        "facility_id": row.facility_id,
    } for result in results for row in result.records]
    return {
        "edges_per_scenario": count, "nodes_per_scenario": count + 1,
        "demand_count": demand_count, "scenario_count": 2,
        "elapsed_seconds_with_tracing": round(elapsed, 6),
        "peak_traced_python_bytes": peak,
        "result_sha256": hashlib.sha256(json.dumps(signature, sort_keys=True).encode()).hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--sizes", type=int, nargs="+", default=[1000, 3000, 6000])
    parser.add_argument("--demand-count", type=int, default=200)
    parser.add_argument("--reference-module", help="Optional module containing the previous engine")
    args = parser.parse_args()
    if any(size <= 0 for size in args.sizes) or args.demand_count <= 0:
        parser.error("Sizes and demand count must be positive.")
    engines = {"current": MPYYMultimodalAccessibilityEngine}
    if args.reference_module:
        engines["reference"] = importlib.import_module(args.reference_module).MPYYMultimodalAccessibilityEngine
    runs = {}
    for name, engine in engines.items():
        runs[name] = []
        for count in args.sizes:
            row = measure(engine, count, args.demand_count)
            runs[name].append(row)
            print(name, count, row["elapsed_seconds_with_tracing"], row["peak_traced_python_bytes"], flush=True)
    comparisons = []
    if "reference" in runs:
        for current, reference in zip(runs["current"], runs["reference"]):
            assert current["result_sha256"] == reference["result_sha256"]
            comparisons.append({
                "edges_per_scenario": current["edges_per_scenario"],
                "results_identical": True,
                "peak_python_memory_ratio": round(current["peak_traced_python_bytes"] /
                                                  reference["peak_traced_python_bytes"], 6),
                "elapsed_ratio": round(current["elapsed_seconds_with_tracing"] /
                                       reference["elapsed_seconds_with_tracing"], 6),
            })
    payload = {
        "qgis_version": Qgis.QGIS_VERSION,
        "fixture": "Synthetic directed chain alternating WALK and TRANSIT; shared-origin demand",
        "limitations": "Python tracemalloc excludes native QGIS/GEOS memory and adds timing overhead; single runs.",
        "runs": runs, "comparisons": comparisons,
        "engine_source_sha256": {
            name: hashlib.sha256(Path(importlib.import_module(engine.__module__).__file__).read_bytes()).hexdigest()
            for name, engine in engines.items()
        },
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

"""Value-based regression coverage for scenario routing and dictionary import."""

import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from qgis.core import (
    QgsApplication, QgsFeature, QgsGeometry, QgsProcessingContext,
    QgsProcessingException, QgsProcessingFeedback, QgsVectorLayer,
)

from . import _DLL_HANDLES
from ..core.accessibility_scenarios import MPYYAccessibilityScenarioEngine
from ..core.digital_governance import MPYYGeoPackageProfileEngine
from ..core.multimodal_accessibility import MPYYMultimodalAccessibilityEngine
from ..core.schema_profile_import import MPYYSchemaProfileImportEngine
from ..core.profile_identity import MPYYProfileIdentityEngine, profile_content_hash, read_profile_json
from ..provider import (
    AuditMPYYSchemaProfileIdentityAlgorithm, CompareMPYYAccessibilityScenariosAlgorithm,
    ImportMPYYGeoPackageSchemaProfileAlgorithm,
)

APP = QgsApplication.instance() or QgsApplication([], False)
APP.initQgis()


def layer(kind, rows, fields="", crs="EPSG:5254"):
    result = QgsVectorLayer(kind + "?crs=" + crs + fields, "fixture", "memory")
    for wkt, attributes in rows:
        feature = QgsFeature(result.fields())
        feature.setGeometry(QgsGeometry.fromWkt(wkt))
        feature.setAttributes(attributes)
        result.dataProvider().addFeature(feature)
    return result


def network(direction="FT", speed=6.0, crs="EPSG:5254"):
    return layer("LineString", [("LINESTRING(0 0,100 0)", ["WALK", speed, direction])],
                 "&field=mode:string&field=speed_kmh:double&field=direction:string", crs)


class ScenarioProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_one_way_routes_are_from_demand_to_facility(self):
        first = layer("Point", [("POINT(0 0)", [])])
        last = layer("Point", [("POINT(100 0)", [])])
        for direction, expected_forward in (("FT", True), ("FORWARD", True),
                                            ("TF", False), ("REVERSE", False), ("BOTH", True)):
            with self.subTest(direction=direction):
                graph = network(direction)
                result = MPYYMultimodalAccessibilityEngine.analyze(
                    graph.getFeatures(), first.getFeatures(), last.getFeatures(), 2.0
                )
                self.assertEqual(result.accessible_count, int(expected_forward))
                reverse = MPYYMultimodalAccessibilityEngine.analyze(
                    graph.getFeatures(), last.getFeatures(), first.getFeatures(), 2.0
                )
                self.assertEqual(reverse.accessible_count, int(not expected_forward or direction == "BOTH"))
                if expected_forward:
                    self.assertAlmostEqual(result.records[0].route_time_min, 1.0)

    def test_multimodal_order_and_explicit_segment_costs(self):
        graph = layer("LineString", [
            ("LINESTRING(0 0,25 0,100 0)", ["WALK", 4.0, "FT"]),
            ("LINESTRING(100 0,200 0)", ["TRANSIT", 2.0, "FT"]),
        ], "&field=mode:string&field=travel_time_min:double&field=direction:string")
        demand = layer("Point", [("POINT(0 0)", [])])
        facilities = layer("Point", [("POINT(200 0)", [])])
        result = MPYYMultimodalAccessibilityEngine.analyze(
            graph.getFeatures(), demand.getFeatures(), facilities.getFeatures(), 10.0,
            transfer_penalty_min=3.0
        )
        self.assertAlmostEqual(result.records[0].route_time_min, 9.0)
        self.assertEqual(result.records[0].modes, "WALK>TRANSIT")

    def test_scenario_changes_and_shared_demand_iterator(self):
        graph_a, graph_b = network("FT", 6.0), network("FT", 12.0)
        demand = layer("Point", [("POINT(0 0)", []), ("POINT(0 1000)", [])])
        facilities = layer("Point", [("POINT(100 0)", [])])
        result = MPYYAccessibilityScenarioEngine.compare(
            graph_a.getFeatures(), graph_b.getFeatures(), demand.getFeatures(),
            facilities.getFeatures(), facilities.getFeatures(), 0.75
        )
        self.assertEqual(len(result.records), 2)
        row = result.records[0]
        self.assertEqual((row.baseline.status, row.proposed.status), ("INACCESSIBLE", "ACCESSIBLE"))
        self.assertEqual(row.change, "FASTER")
        self.assertAlmostEqual(row.time_change_min, -0.5)
        self.assertEqual(result.records[1].change, "SNAP_REVIEW")
        self.assertIsNone(result.records[1].time_change_min)

    def test_scenario_route_loss_gain_and_empty_facilities(self):
        demand = layer("Point", [("POINT(0 0)", [])])
        facilities = layer("Point", [("POINT(100 0)", [])])
        empty = layer("Point", [])
        for direction_a, direction_b, facilities_b, expected in (
            ("TF", "FT", facilities, "NEWLY_REACHABLE"),
            ("FT", "TF", facilities, "LOST_ROUTE"),
            ("TF", "TF", facilities, "STILL_UNREACHABLE"),
            ("FT", "FT", empty, "LOST_ROUTE"),
            ("FT", "FT", facilities, "UNCHANGED"),
        ):
            with self.subTest(expected=expected):
                graph_a, graph_b = network(direction_a), network(direction_b)
                result = MPYYAccessibilityScenarioEngine.compare(
                    graph_a.getFeatures(), graph_b.getFeatures(), demand.getFeatures(),
                    facilities.getFeatures(), facilities_b.getFeatures(), 2.0
                )
                self.assertEqual(result.records[0].change, expected)
                self.assertEqual(result.records[0].time_change_min, 0.0 if expected == "UNCHANGED" else None)

    def parameters(self):
        return {
            "NETWORK_A": network("FT", 6.0), "NETWORK_B": network("FT", 12.0),
            "DEMAND": layer("Point", [("POINT(0 0)", [])]),
            "FACILITIES_A": layer("Point", [("POINT(100 0)", [])]),
            "FACILITIES_B": layer("Point", [("POINT(100 0)", [])]),
            "MODE_FIELD": "mode", "SPEED_FIELD": "speed_kmh",
            "TRAVEL_TIME_FIELD": "travel_time_min", "DIRECTION_FIELD": "direction",
            "MAX_TIME_MIN": 0.75, "WALK_SPEED_KMH": 4.8, "BICYCLE_SPEED_KMH": 15.0,
            "TRANSIT_SPEED_KMH": 25.0, "TRANSFER_PENALTY_MIN": 3.0,
            "SNAP_TOLERANCE": 1.0, "MAX_SNAP_DISTANCE": 50.0, "OUTPUT": "memory:changes",
        }

    def test_scenario_processing_output_values(self):
        algorithm = CompareMPYYAccessibilityScenariosAlgorithm()
        algorithm.initAlgorithm()
        parameters = self.parameters()
        context = QgsProcessingContext()
        response = algorithm.processAlgorithm(parameters, context, QgsProcessingFeedback())
        self.assertEqual(response["CHANGE_COUNTS"], {"FASTER": 1})
        output = context.getMapLayer(response["OUTPUT"])
        row = next(output.getFeatures())
        self.assertEqual(row["change"], "FASTER")
        self.assertAlmostEqual(row["time_a_min"], 1.0)
        self.assertAlmostEqual(row["time_b_min"], 0.5)
        self.assertAlmostEqual(row["time_change_min"], -0.5)
        self.assertTrue(row.geometry().equals(next(parameters["DEMAND"].getFeatures()).geometry()))

    def test_scenario_processing_rejects_crs_and_missing_mode(self):
        algorithm = CompareMPYYAccessibilityScenariosAlgorithm()
        algorithm.initAlgorithm()
        for crs in ("EPSG:4326", "EPSG:2263", "EPSG:3857"):
            parameters = self.parameters()
            parameters["NETWORK_A"] = network(crs=crs)
            with self.subTest(crs=crs), self.assertRaises(QgsProcessingException):
                algorithm.processAlgorithm(parameters, QgsProcessingContext(), QgsProcessingFeedback())
        parameters = self.parameters()
        parameters["MODE_FIELD"] = "missing"
        with self.assertRaises(QgsProcessingException):
            algorithm.processAlgorithm(parameters, QgsProcessingContext(), QgsProcessingFeedback())

    def dictionary(self):
        source = self.root / "dictionary.csv"
        source.write_text("table,column,datatype,pk,required\nplan,id,INTEGER,true,true\nplan,code,TEXT,false,true\n",
                          encoding="utf-8-sig")
        mapping = {
            "profile_id": "EXAMPLE_ONLY", "profile_version": "1",
            "source_institution": "Example institution", "source_reference": "Example dictionary v1",
            "columns": {"table": "table", "field": "column", "type": "datatype",
                        "primary_key": "pk", "not_null": "required"},
        }
        return source, mapping

    def test_dictionary_profile_identity_and_actual_schema_audit(self):
        source, mapping = self.dictionary()
        profile = MPYYSchemaProfileImportEngine.convert(source, mapping)
        self.assertEqual(profile, MPYYSchemaProfileImportEngine.convert(source, mapping))
        self.assertEqual(profile["source_sha256"], hashlib.sha256(source.read_bytes()).hexdigest())
        self.assertEqual(profile["import_mapping"], mapping)
        payload = {key: value for key, value in profile.items() if key != "content_sha256"}
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        self.assertEqual(profile["content_sha256"], hashlib.sha256(canonical.encode()).hexdigest())
        gpkg = self.root / "fixture.gpkg"
        with sqlite3.connect(gpkg) as connection:
            connection.execute("CREATE TABLE plan (id INTEGER PRIMARY KEY, code TEXT NOT NULL)")
        original = gpkg.read_bytes()
        self.assertEqual(MPYYGeoPackageProfileEngine.audit(gpkg, profile).status, "COMPLETE")
        self.assertEqual(gpkg.read_bytes(), original)
        with sqlite3.connect(gpkg) as connection:
            connection.execute("DROP TABLE plan")
            connection.execute("CREATE TABLE plan (id INTEGER NOT NULL, code TEXT NOT NULL)")
        result = MPYYGeoPackageProfileEngine.audit(gpkg, profile)
        self.assertIn("FIELD_PRIMARY_KEY_MISMATCH", {item.code for item in result.findings})

    def test_dictionary_rejects_ambiguous_and_malformed_sources(self):
        source, mapping = self.dictionary()
        for csv_text in (
            "table,column,datatype,pk,required\nplan,id,INTEGER,maybe,true\n",
            "table,column,datatype,pk,required\nplan,id,INTEGER,true,true\nplan,id,TEXT,false,true\n",
            "table,column,datatype,pk,required\nplan,id,INTEGER\n",
            "table,column,datatype,pk,required\n",
            "table,column,datatype,pk,required,table\nplan,id,INTEGER,true,true,other\n",
        ):
            with self.subTest(csv=csv_text), self.assertRaises(ValueError):
                source.write_text(csv_text, encoding="utf-8")
                MPYYSchemaProfileImportEngine.convert(source, mapping)
        source, mapping = self.dictionary()
        mapping.pop("source_reference")
        with self.assertRaises(ValueError):
            MPYYSchemaProfileImportEngine.convert(source, mapping)

    def test_dictionary_geometry_and_conflicting_srs(self):
        source, mapping = self.dictionary()
        mapping["columns"].update({"geometry_type": "geometry", "srs_id": "srs"})
        source.write_text("table,column,datatype,pk,required,geometry,srs\n"
                          "plan,id,INTEGER,true,true,POLYGON,5254\n"
                          "plan,code,TEXT,false,true,POLYGON,5254\n", encoding="utf-8")
        profile = MPYYSchemaProfileImportEngine.convert(source, mapping)
        self.assertEqual(profile["tables"][0]["srs_id"], 5254)
        source.write_text(source.read_text().replace("code,TEXT,false,true,POLYGON,5254",
                                                     "code,TEXT,false,true,POLYGON,3857"), encoding="utf-8")
        with self.assertRaises(ValueError):
            MPYYSchemaProfileImportEngine.convert(source, mapping)

    def test_profile_self_identity_and_independent_pin(self):
        source, mapping = self.dictionary()
        profile = MPYYSchemaProfileImportEngine.convert(source, mapping)
        result = MPYYProfileIdentityEngine.audit(profile, source, profile["content_sha256"])
        self.assertEqual(result.status, "COMPLETE")
        self.assertTrue(result.details["source_bytes_verified"])
        self.assertTrue(result.details["dictionary_reconstruction_verified"])
        self.assertEqual(result.details["issuer_authenticity"], "NOT_VERIFIED")
        profile["tables"][0]["fields"][0]["type"] = "BLOB"
        result = MPYYProfileIdentityEngine.audit(profile)
        self.assertIn("PROFILE_HASH_MISMATCH", {item.code for item in result.findings})
        original_pin = profile["content_sha256"]
        profile["content_sha256"] = profile_content_hash(profile)
        result = MPYYProfileIdentityEngine.audit(profile, source, original_pin)
        self.assertIn("EXPECTED_PROFILE_HASH_MISMATCH", {item.code for item in result.findings})
        self.assertIn("DICTIONARY_PROFILE_MISMATCH", {item.code for item in result.findings})
        self.assertTrue(result.details["source_bytes_verified"])

    def test_changed_dictionary_bytes_are_detected(self):
        source, mapping = self.dictionary()
        profile = MPYYSchemaProfileImportEngine.convert(source, mapping)
        source.write_bytes(source.read_bytes() + b"\n")
        result = MPYYProfileIdentityEngine.audit(profile, source)
        self.assertEqual(result.status, "INCOMPLETE")
        self.assertIn("SOURCE_DICTIONARY_HASH_MISMATCH", {item.code for item in result.findings})
        self.assertFalse(result.details["dictionary_reconstruction_verified"])

    def test_profile_hash_guard_and_legacy_profile_compatibility(self):
        source, mapping = self.dictionary()
        profile = MPYYSchemaProfileImportEngine.convert(source, mapping)
        gpkg = self.root / "guard.gpkg"
        with sqlite3.connect(gpkg) as connection:
            connection.execute("CREATE TABLE plan (id INTEGER PRIMARY KEY, code TEXT NOT NULL)")
        original = gpkg.read_bytes()
        profile["profile_version"] = "tampered"
        result = MPYYGeoPackageProfileEngine.audit(gpkg, profile)
        self.assertEqual(result.status, "INCOMPLETE")
        self.assertEqual(result.details["checked_table_count"], 0)
        self.assertEqual(gpkg.read_bytes(), original)
        profile.pop("content_sha256")
        result = MPYYGeoPackageProfileEngine.audit(gpkg, profile)
        self.assertIn("MISSING_OR_INVALID_PROFILE_HASH", {item.code for item in result.findings})
        legacy = {"profile_id": "legacy", "profile_version": "1", "tables": profile["tables"]}
        self.assertEqual(MPYYGeoPackageProfileEngine.audit(gpkg, legacy).status, "COMPLETE")
        self.assertEqual(MPYYProfileIdentityEngine.audit(legacy).status, "INCOMPLETE")

    def test_profile_rejects_invalid_digest_source_and_metadata(self):
        source, mapping = self.dictionary()
        profile = MPYYSchemaProfileImportEngine.convert(source, mapping)
        for key, value, expected in (
            ("content_sha256", 12, "MISSING_OR_INVALID_PROFILE_HASH"),
            ("source_sha256", "not-a-hash", "MISSING_OR_INVALID_SOURCE_HASH"),
            ("profile_id", "", "INVALID_PROFILE_METADATA"),
            ("tables", [], "INVALID_PROFILE_TABLES"),
        ):
            with self.subTest(key=key):
                altered = {**profile, key: value}
                self.assertIn(expected, {item.code for item in MPYYProfileIdentityEngine.audit(altered).findings})
        self.assertIn("INVALID_EXPECTED_PROFILE_HASH", {
            item.code for item in MPYYProfileIdentityEngine.audit(profile, expected_sha256="bad").findings
        })

    def test_profile_strict_json_loader(self):
        path = self.root / "invalid.json"
        for text in ('{"profile_id":"a","profile_id":"b"}',
                     '{"columns":{"table":"a","table":"b"}}',
                     '{"value":NaN}', '{"value":Infinity}', '[]'):
            path.write_text(text, encoding="utf-8")
            with self.subTest(text=text), self.assertRaises(ValueError):
                read_profile_json(path)
        path.write_text('{"profile_id":"a"}', encoding="utf-8-sig")
        self.assertEqual(read_profile_json(path)["profile_id"], "a")

    def test_profile_identity_processing_and_report_hash(self):
        source, mapping = self.dictionary()
        profile = MPYYSchemaProfileImportEngine.convert(source, mapping)
        path = self.root / "profile.json"
        MPYYSchemaProfileImportEngine.write(profile, path)
        output = self.root / "identity.json"
        algorithm = AuditMPYYSchemaProfileIdentityAlgorithm()
        algorithm.initAlgorithm()
        parameters = {"PROFILE": str(path), "DICTIONARY": str(source),
                      "EXPECTED_SHA256": profile["content_sha256"], "OUTPUT_REPORT": str(output)}
        response = algorithm.processAlgorithm(parameters, QgsProcessingContext(), QgsProcessingFeedback())
        self.assertEqual(response["STATUS"], "COMPLETE")
        report = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(report["content_sha256"], profile_content_hash(report))
        self.assertEqual(response["COMPUTED_SHA256"], profile["content_sha256"])
        parameters["DICTIONARY"] = None
        parameters["EXPECTED_SHA256"] = None
        response = algorithm.processAlgorithm(parameters, QgsProcessingContext(), QgsProcessingFeedback())
        self.assertEqual(response["STATUS"], "COMPLETE")
        original = path.read_bytes()
        parameters["OUTPUT_REPORT"] = str(path)
        with self.assertRaises(QgsProcessingException):
            algorithm.processAlgorithm(parameters, QgsProcessingContext(), QgsProcessingFeedback())
        self.assertEqual(path.read_bytes(), original)

    def test_long_alternating_mode_chain_has_exact_cost_and_order(self):
        count = 3000
        graph = layer("LineString", [
            (f"LINESTRING({index} 0,{index + 1} 0)", ["WALK" if index % 2 == 0 else "TRANSIT", 60.0, "FT"])
            for index in range(count)
        ], "&field=mode:string&field=speed_kmh:double&field=direction:string")
        demand = layer("Point", [("POINT(0 0)", []), ("POINT(0 0)", [])])
        facilities = layer("Point", [(f"POINT({count} 0)", [])])
        result = MPYYMultimodalAccessibilityEngine.analyze(
            graph.getFeatures(), demand.getFeatures(), facilities.getFeatures(), 10000.0,
            transfer_penalty_min=0.5, snap_tolerance_m=0.1
        )
        self.assertEqual(result.graph_node_count, count + 1)
        self.assertEqual(result.graph_edge_count, count)
        self.assertAlmostEqual(result.records[0].route_time_min, count / 1000.0 + (count - 1) * 0.5)
        self.assertEqual(result.records[0].modes, ">".join(["WALK", "TRANSIT"] * (count // 2)))
        self.assertIs(result.records[0].modes, result.records[1].modes)

    def test_accessibility_cancellation_during_graph_and_search(self):
        graph = network()
        demand = layer("Point", [("POINT(0 0)", [])])
        facilities = layer("Point", [("POINT(100 0)", [])])
        for limit in (1, 3, 6):
            calls = 0

            def canceled():
                nonlocal calls
                calls += 1
                return calls >= limit

            with self.subTest(limit=limit), self.assertRaisesRegex(ValueError, "canceled"):
                MPYYMultimodalAccessibilityEngine.analyze(
                    graph.getFeatures(), demand.getFeatures(), facilities.getFeatures(), 2.0,
                    cancel_check=canceled
                )
            self.assertEqual(calls, limit)
        algorithm = CompareMPYYAccessibilityScenariosAlgorithm()
        algorithm.initAlgorithm()
        feedback = QgsProcessingFeedback()
        feedback.cancel()
        with self.assertRaisesRegex(QgsProcessingException, "canceled"):
            algorithm.processAlgorithm(self.parameters(), QgsProcessingContext(), feedback)

    def test_dictionary_processing_and_input_preservation(self):
        source, mapping = self.dictionary()
        mapping_path = self.root / "mapping.json"
        mapping_path.write_text(json.dumps(mapping), encoding="utf-8")
        output = self.root / "profile.json"
        algorithm = ImportMPYYGeoPackageSchemaProfileAlgorithm()
        algorithm.initAlgorithm()
        parameters = {"DICTIONARY": str(source), "MAPPING": str(mapping_path), "OUTPUT_PROFILE": str(output)}
        response = algorithm.processAlgorithm(parameters, QgsProcessingContext(), QgsProcessingFeedback())
        self.assertEqual(response["TABLE_COUNT"], 1)
        self.assertEqual(response["FIELD_COUNT"], 2)
        self.assertEqual(json.loads(output.read_text())["content_sha256"], response["CONTENT_SHA256"])
        original = source.read_bytes()
        parameters["OUTPUT_PROFILE"] = str(source)
        with self.assertRaises(QgsProcessingException):
            algorithm.processAlgorithm(parameters, QgsProcessingContext(), QgsProcessingFeedback())
        self.assertEqual(source.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()

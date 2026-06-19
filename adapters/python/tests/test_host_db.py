import tempfile
import unittest
from pathlib import Path

from jsonschema.exceptions import ValidationError

from urirun import host_db, v2


class HostDbTests(unittest.TestCase):
    def test_dataset_schema_and_record_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "host.db")
            schema = {
                "type": "object",
                "required": ["domain"],
                "properties": {"domain": {"type": "string"}, "url": {"type": "string"}},
                "additionalProperties": False,
            }
            dataset = host_db.create_dataset(db, "domains", "Managed domains", schema)
            self.assertEqual(dataset["name"], "domains")

            with self.assertRaises(ValidationError):
                host_db.upsert_record(db, "domains", "bad", {"url": "https://ifuri.com"})

            record = host_db.upsert_record(
                db,
                "domains",
                "ifuri.com",
                {"domain": "ifuri.com", "url": "https://ifuri.com"},
                source_uri="task://host/ticket/command/create",
                confidence=0.9,
            )
            self.assertEqual(record["key"], "ifuri.com")

            found = host_db.search_records(db, "ifuri")
            self.assertEqual(found[0]["key"], "ifuri.com")

    def test_v2_data_uri_bindings(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "host.db")
            registry = v2.compile_registry(v2.host_data_bindings(db=db))

            dataset = v2.run(
                "data://host/dataset/command/create",
                registry,
                {
                    "name": "domains",
                    "schema": {
                        "type": "object",
                        "required": ["domain"],
                        "properties": {"domain": {"type": "string"}},
                    },
                },
                mode="execute",
            )
            self.assertTrue(dataset["ok"], dataset)

            dry = v2.run(
                "data://host/record/command/upsert",
                registry,
                {"dataset": "domains", "key": "ifuri.com", "data": {"domain": "ifuri.com"}},
                mode="dry-run",
            )
            self.assertTrue(dry["ok"], dry)
            self.assertTrue(dry["result"]["simulated"])
            self.assertEqual(host_db.search_records(db, "ifuri"), [])

            upserted = v2.run(
                "data://host/record/command/upsert",
                registry,
                {"dataset": "domains", "key": "ifuri.com", "data": {"domain": "ifuri.com"}},
                mode="execute",
            )
            self.assertTrue(upserted["ok"], upserted)

            searched = v2.run(
                "data://host/records/query/search",
                registry,
                {"query": "ifuri", "dataset": "domains"},
            )
            self.assertTrue(searched["ok"], searched)
            self.assertEqual(searched["result"]["records"][0]["key"], "ifuri.com")

    def test_artifact_and_check_storage(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "host.db")
            artifact = host_db.register_artifact(
                db,
                "screenshot",
                "artifact://host/screenshot/ifuri",
                "/tmp/ifuri.png",
                {"subject": "ifuri.com"},
            )
            self.assertEqual(artifact["kind"], "screenshot")

            check = host_db.add_check(
                db,
                "ifuri.com",
                "monitor://ifuri.com/http/query/status",
                "ok",
                {"status": 200},
            )
            self.assertEqual(check["result"], {"status": 200})
            self.assertEqual(host_db.recent_checks(db, subject="ifuri.com")[0]["id"], check["id"])


if __name__ == "__main__":
    unittest.main()

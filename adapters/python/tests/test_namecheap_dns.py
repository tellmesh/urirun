import tempfile
import unittest
from pathlib import Path

from urirun import host_db, namecheap_dns, v2


GET_HOSTS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<ApiResponse Status="OK" xmlns="http://api.namecheap.com/xml.response">
  <CommandResponse Type="namecheap.domains.dns.getHosts">
    <DomainDNSGetHostsResult Domain="example.com" IsUsingOurDNS="true">
      <host HostId="1" Name="@" Type="A" Address="203.0.113.10" TTL="1800" />
      <host HostId="2" Name="www" Type="CNAME" Address="example.com" TTL="1800" />
    </DomainDNSGetHostsResult>
  </CommandResponse>
</ApiResponse>
"""


class NamecheapDnsTests(unittest.TestCase):
    def test_parse_get_hosts_xml(self):
        parsed = namecheap_dns.parse_api_xml(GET_HOSTS_XML)

        self.assertTrue(parsed["ok"], parsed)
        self.assertEqual(
            parsed["records"],
            [
                {"Name": "@", "Type": "A", "Address": "203.0.113.10", "TTL": "1800"},
                {"Name": "www", "Type": "CNAME", "Address": "example.com", "TTL": "1800"},
            ],
        )

    def test_plan_merges_ensure_and_remove_records(self):
        result = namecheap_dns.plan(
            "example.com",
            {
                "current_records": [
                    {"Name": "@", "Type": "A", "Address": "203.0.113.10", "TTL": 1800},
                    {"Name": "old", "Type": "A", "Address": "203.0.113.20"},
                ],
                "ensure_records": [{"Name": "www", "Type": "CNAME", "Address": "example.com"}],
                "remove_records": [{"Name": "old", "Type": "A", "Address": "203.0.113.20"}],
            },
        )

        self.assertTrue(result["ok"])
        self.assertTrue(result["diff"]["changed"])
        self.assertEqual(result["diff"]["added"], [{"Name": "www", "Type": "CNAME", "Address": "example.com"}])
        self.assertEqual(result["diff"]["removed"], [{"Name": "old", "Type": "A", "Address": "203.0.113.20"}])
        self.assertTrue(result["destructive"])

    def test_backup_writes_artifact_and_registers_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "host.db")
            out_dir = str(Path(tmp) / "backups")
            artifact = namecheap_dns.backup(
                "example.com",
                [{"Name": "@", "Type": "A", "Address": "203.0.113.10"}],
                db=db,
                out_dir=out_dir,
            )

            self.assertEqual(artifact["kind"], "dns-backup")
            self.assertTrue(Path(artifact["path"]).exists())
            self.assertEqual(host_db.list_artifacts(db, kind="dns-backup")[0]["uri"], artifact["uri"])

    def test_apply_requires_backup_uri(self):
        with self.assertRaisesRegex(ValueError, "backup_uri"):
            namecheap_dns.apply(
                "example.com",
                {
                    "confirm": True,
                    "current_records": [{"Name": "@", "Type": "A", "Address": "203.0.113.10"}],
                    "desired_records": [{"Name": "@", "Type": "A", "Address": "203.0.113.11"}],
                    "mock_apply": True,
                },
            )

    def test_apply_mock_refuses_current_drift_from_reviewed_plan(self):
        plan = namecheap_dns.plan(
            "example.com",
            {
                "current_records": [{"Name": "@", "Type": "A", "Address": "203.0.113.10"}],
                "desired_records": [{"Name": "@", "Type": "A", "Address": "203.0.113.11"}],
            },
        )

        with self.assertRaisesRegex(ValueError, "differ"):
            namecheap_dns.apply(
                "example.com",
                {
                    "confirm": True,
                    "backup_uri": "artifact://host/namecheap/dns-backup/example.com/test",
                    "plan": plan,
                    "current_records": [{"Name": "@", "Type": "A", "Address": "203.0.113.99"}],
                    "mock_apply": True,
                },
            )

    def test_v2_dns_namecheap_uri_plan_backup_apply_mock(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "host.db")
            registry = v2.compile_registry(v2.domain_monitor_bindings(db=db, project=tmp, screenshot_dir=str(Path(tmp) / "shots")))
            current = [{"Name": "@", "Type": "A", "Address": "203.0.113.10", "TTL": 1800}]
            desired = [{"Name": "@", "Type": "A", "Address": "203.0.113.11", "TTL": 1800}]

            plan_result = v2.run(
                "dns://host/records/command/plan",
                registry,
                {
                    "provider": "namecheap",
                    "domain": "example.com",
                    "current_records": current,
                    "desired_records": desired,
                },
            )
            self.assertTrue(plan_result["ok"], plan_result)
            self.assertEqual(plan_result["result"]["action"], "plan")
            self.assertTrue(plan_result["result"]["diff"]["changed"])

            backup_result = v2.run(
                "dns://host/records/command/backup",
                registry,
                {
                    "provider": "namecheap",
                    "domain": "example.com",
                    "current_records": current,
                    "backup_dir": str(Path(tmp) / "backups"),
                },
                mode="execute",
            )
            self.assertTrue(backup_result["ok"], backup_result)
            backup_uri = backup_result["result"]["backup"]["uri"]

            apply_result = v2.run(
                "dns://host/records/command/apply",
                registry,
                {
                    "provider": "namecheap",
                    "domain": "example.com",
                    "current_records": current,
                    "plan": plan_result["result"],
                    "backup_uri": backup_uri,
                    "confirm": True,
                    "mock_apply": True,
                },
                mode="execute",
            )
            self.assertTrue(apply_result["ok"], apply_result)
            self.assertEqual(apply_result["result"]["action"], "apply")
            self.assertTrue(apply_result["result"]["mock"])


if __name__ == "__main__":
    unittest.main()

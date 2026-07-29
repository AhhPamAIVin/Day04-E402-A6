from __future__ import annotations

import json
import unittest
from pathlib import Path

from tools import TOOL_FUNCTIONS, load_tool_declarations
from tools.policy.tool import POLICY_DIR, search_company_policy
from tools.policy_compare.tool import compare_policy_sections


ROOT = Path(__file__).resolve().parents[1]


class CompanyPolicyProjectTests(unittest.TestCase):
    def test_internal_policy_corpus_has_ten_documents(self) -> None:
        documents = sorted(POLICY_DIR.glob("*.md"))
        self.assertEqual(len(documents), 10)
        self.assertTrue(all(path.parent.name == "internal-policies" for path in documents))

    def test_leave_search_returns_specific_section_and_source(self) -> None:
        result = search_company_policy(
            "nhân viên trên 5 năm có bao nhiêu ngày nghỉ phép năm",
            policy_area="leave",
            top_k=3,
        )
        self.assertFalse(result.get("error"))
        self.assertTrue(result["results"])
        first = result["results"][0]
        self.assertEqual(first["policy_area"], "leave")
        self.assertIn("Nghỉ phép năm", first["section"])
        self.assertEqual(
            first["source_path"],
            "internal-policies/02_Leave_Policy.md",
        )

    def test_it_security_search_uses_internal_mock_data(self) -> None:
        result = search_company_policy(
            "mật khẩu tối thiểu 12 ký tự đổi 90 ngày",
            policy_area="it_security",
            top_k=2,
        )
        self.assertTrue(result["results"])
        self.assertEqual(
            result["results"][0]["source_path"],
            "internal-policies/04_IT_Security_Policy.md",
        )

    def test_policy_compare_preserves_evidence_sources(self) -> None:
        result = compare_policy_sections([
            {
                "doc_id": "equipment",
                "policy_area": "equipment",
                "title": "Chính sách thiết bị",
                "section": "Xử lý sự cố",
                "facts": "Mất thiết bị phải báo IT trong 24 giờ.",
                "source_path": "internal-policies/09_Equipment_Policy.md",
            },
            {
                "doc_id": "conduct",
                "policy_area": "code_of_conduct",
                "title": "Quy tắc ứng xử",
                "section": "Hành vi nơi làm việc",
                "facts": "Sự cố quấy rối phải báo HR trong 48 giờ.",
                "source_path": "internal-policies/08_Code_of_Conduct.md",
            },
        ], comparison_focus="thời hạn báo cáo")
        self.assertIsNone(result["error"])
        self.assertEqual(result["section_count"], 2)
        self.assertEqual(
            {source["source_path"] for source in result["sources"]},
            {
                "internal-policies/09_Equipment_Policy.md",
                "internal-policies/08_Code_of_Conduct.md",
            },
        )

    def test_group_eval_has_exact_required_shape(self) -> None:
        data = json.loads(
            (ROOT / "data" / "eval_group.json").read_text(encoding="utf-8")
        )
        cases = data["cases"]
        self.assertEqual(len(cases), 10)
        self.assertEqual(sum("query" in case for case in cases), 5)
        self.assertEqual(sum("turns" in case for case in cases), 5)
        self.assertEqual(len({case["id"] for case in cases}), 10)
        for case in cases:
            self.assertEqual(case["phase"], "B")
            self.assertTrue(case["metadata"]["what_it_tests"])
            if "turns" in case:
                self.assertEqual(case["turns"][-1]["role"], "user")

    def test_declared_tools_are_implemented(self) -> None:
        declarations = load_tool_declarations(ROOT / "artifacts" / "tools.yaml")
        declared = {item["name"] for item in declarations}
        self.assertGreaterEqual(len(declared), 5)
        self.assertIn("policy", declared)
        self.assertIn("policy_compare", declared)
        self.assertTrue(declared.issubset(TOOL_FUNCTIONS))


if __name__ == "__main__":
    unittest.main()

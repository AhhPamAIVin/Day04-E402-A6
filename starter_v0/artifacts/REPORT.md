# Day 04 Lab v2 Report — TechNova Company Policy Assistant

> Báo cáo này đã hoàn thiện nội dung mô tả, phân công, eval design, failure
> analysis và demo plan. Trước khi nộp, nhóm chỉ cần điền họ tên/mã sinh viên,
> public URL và số liệu v2–v3 sau khi chạy OpenAI.

## Thông tin nhóm

- **Tên đề tài:** Company Policy Assistant
- **Mô tả:** Trợ lý tra cứu quy định nội bộ TechNova Solutions và trả lời kèm
  section, đường dẫn tài liệu và bằng chứng.
- **Provider/model:** OpenAI / `gpt-4o-mini`
- **Dữ liệu chính:** `internal-policies/*.md` — 10 tài liệu mock policy

| STT | Họ và tên | Mã sinh viên | Vai trò | Phần phụ trách chính | Evidence/file |
|---:|---|---|---|---|---|
| 1 | Phạm Tuấn Anh | 2A202601072 | Tool Engineer | Hoàn thiện `policy`, xây `policy_compare`, registry và smoke test | `tools/policy/`, `tools/policy_compare/` |
| 2 | Tống Duy An | 2A202601995 | Prompt Engineer | Routing, citation, clarification, guardrail và multi-turn | `artifacts/system_prompt.md`, `artifacts/tools.yaml` |
| 3 | Ngô Mạnh Minh Huy | 2A202601926 | Evaluation Engineer | 10 group cases, chạy v0–v3, phân tích failure và metric | `data/eval_group.json`, `runs/`, `version_log.csv` |
| 4 | Đào Bình Minh | 2A202601364 | Mock Data Engineer | Xây, kiểm tra và mô tả 10 tài liệu policy TechNova | `internal-policies/` |
| 5 | Ngô Trọng Bảo | 2A202601024 | UI & Report Engineer | Streamlit UI, tool trace, transcript, demo và tổng hợp báo cáo | `app.py`, `transcripts/`, `REPORT.md` |

---

# PHẦN A — Giới thiệu agent

## A1. Agent làm được gì?

TechNova Company Policy Assistant giúp nhân viên tra cứu quy định về nghỉ phép,
làm việc từ xa, bảo mật CNTT, chi phí, công tác, hiệu suất, ứng xử, thiết bị và
quyền riêng tư dữ liệu. Agent chỉ kết luận trong phạm vi bằng chứng tìm thấy và
luôn hiển thị tên tài liệu, section và `source_path`.

Agent cũng có thể so sánh từ hai policy section trở lên bằng tool mới
`policy_compare`. Các “possible tensions” chỉ được xem là tín hiệu cần con
người review, không phải kết luận pháp lý hay quyết định quản lý.

**Link dùng thử:**

- Local: `http://localhost:8501`
- Public URL khi showdown: `[Điền URL deploy hoặc trycloudflare.com]`

## A2. Tool agent sử dụng

| Tool | Chức năng | Phân loại |
|---|---|---|
| `policy` | Tra cứu 10 tài liệu trong `internal-policies/`, trả evidence và nguồn | Built-in được điều chỉnh cho đề tài |
| `policy_compare` | So sánh các policy section đã có, tổng hợp yêu cầu và giữ nguồn | **Tool mới của nhóm** |
| `clarify` | Hỏi thông tin bắt buộc hoặc xác nhận trước external write | Core |
| `format` | Định dạng các item đã có thành checklist/digest | Core hỗ trợ |
| `send` | Gửi Telegram sau xác nhận rõ ràng | Optional |
| `timeline`, `social_search`, `lookup`, `fetch` | Các tool research giữ lại để chạy fixed base eval | Core của starter |
| `papers`, `paper_text` | Tìm và đọc paper arXiv | Optional |

## A3. Dữ liệu chính

| Policy area | Tài liệu | Nội dung demo tiêu biểu |
|---|---|---|
| `employee_handbook` | `01_Employee_Handbook.md` | Giờ làm việc, trang phục, thử việc |
| `leave` | `02_Leave_Policy.md` | Nghỉ phép năm, nghỉ ốm, nghỉ khẩn cấp |
| `remote_work` | `03_Remote_Work_Policy.md` | Số ngày remote, phê duyệt, giờ liên lạc |
| `it_security` | `04_IT_Security_Policy.md` | Mật khẩu, USB, VPN |
| `expense_reimbursement` | `05_Expense_Reimbursement.md` | Ăn uống, khách sạn, hóa đơn |
| `travel` | `06_Travel_Policy.md` | Vé công tác trong nước/quốc tế |
| `performance_review` | `07_Performance_Review.md` | Chu kỳ đánh giá và thăng tiến |
| `code_of_conduct` | `08_Code_of_Conduct.md` | Quấy rối và xung đột lợi ích |
| `equipment` | `09_Equipment_Policy.md` | Cấp laptop và báo mất thiết bị |
| `data_privacy` | `10_Data_Privacy_Policy.md` | Dữ liệu khách hàng và lưu trữ tài liệu |

## A4. Câu hỏi mẫu

1. Nhân viên làm trên 5 năm có bao nhiêu ngày nghỉ phép năm?
2. Mật khẩu công ty phải dài tối thiểu bao nhiêu ký tự và đổi bao lâu một lần?
3. Một tuần được remote tối đa mấy ngày và cần duyệt trước bao lâu?
4. Công ty hoàn tối đa bao nhiêu tiền khách sạn mỗi đêm?
5. So sánh yêu cầu sử dụng thiết bị cá nhân trong Data Privacy và IT Security.

## A5. Kịch bản demo đã chuẩn bị

| Scenario | Tool trace cần thấy | Câu chuyện cải tiến | Fallback evidence |
|---|---|---|---|
| Hỏi số ngày nghỉ phép | `policy(policy_area=leave)` và source path | v2 đồng bộ dữ liệu mới; v3 chuẩn hóa citation | Group case `CP_S01` |
| Hỏi mật khẩu | `policy(policy_area=it_security)` | Tool không còn đọc KB mẫu cũ | Group case `CP_S02` |
| Câu “quy định đó” | `clarify(response_type=text)` | Không đoán tài liệu thiếu ngữ cảnh | Group case `CP_S05` |
| User đổi từ mật khẩu sang mất laptop | `policy(policy_area=equipment)` | v3 xử lý correction trong multi-turn | Group case `CP_M03` |
| So sánh hai policy | `policy_compare` và evidence IDs | Tool mới giữ nguồn, tension cần manual review | `CP_S03`, `CP_M05` |

---

# PHẦN B — Chi tiết và bằng chứng

## B1. Version evidence

Metric chỉ hợp lệ khi `provider_error_cases=0` và
`measured_cases=total_cases`. Tool result có error vẫn phải review thủ công.

| Version | Thay đổi | Hypothesis | Case accuracy | Routing | Arguments | Multi-turn | Run |
|---|---|---|---:|---:|---:|---:|---|
| v0 | Baseline starter | Prompt đoán dữ liệu và tool description mơ hồ gây sai routing/boundary | 0.70 | 0.75 | 0.70 | 1.00 | `runs/v0_B_base_openai_20260729T153959843418.json` |
| v1 | Viết lại prompt theo hướng policy, không đoán và không tự gửi | Boundary tốt hơn nhưng routing generic có thể regression | 0.65 | 0.85 | 0.65 | 0.6667 | `runs/v1_B_base_openai_20260729T155931234885.json` |
| v2 | Nối `policy` với `internal-policies`, thêm 10 area và citation contract | Policy routing và nguồn evidence sẽ đúng dữ liệu TechNova | `[Chạy OpenAI]` | `[Điền]` | `[Điền]` | `[Điền]` | `[Điền run v2]` |
| v3 | Bổ sung multi-turn precedence, base-routing regression guard và `policy_compare` | Tăng multi-turn mà không làm giảm routing | `[Chạy OpenAI]` | `[Điền]` | `[Điền]` | `[Điền]` | `[Điền run v3]` |

Script chạy v2–v3:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_policy_versions.ps1
```

## B2. Failure analysis từ log thật

| Version/case | Failure | Actual behavior | Phân tích | Fix áp dụng |
|---|---|---|---|---|
| v0/R10 | `missing_info` | Đoán `sama` khi thiếu tài khoản | Prompt baseline yêu cầu tự đoán | Bắt buộc `clarify(text)` khi thiếu handle |
| v0/R11 | `missing_info` | Tự tạo URL example | Không có missing-URL boundary | Cấm đoán URL, dùng `clarify(text)` |
| v0/R12 | `wrong_boundary` | Gọi `send` ngay | Chưa có confirmation boundary | `clarify(yes_no)` trước external write |
| v0/R08, R14 | `out_of_scope` | Dùng `send` để trả lời toán/code | Tool description `send` quá mơ hồ | Quy định no-tool cho câu ngoài scope |
| v1/R03, R06, R13 | Routing/args | Thiếu hoặc sai `topic=news` | Prompt policy làm yếu mapping fixed base | v3 phục hồi news/timeframe/multi-tool rules |
| v1/M02, M06 | Multi-turn | Giữ sai nguồn social | Chưa có correction/source-switch precedence | v3: latest correction và cancellation override |

## B3. Team-authored eval

File `data/eval_group.json` có đúng **10 case: 5 single-turn + 5 multi-turn**.

| Case ID | Dạng | Nội dung kiểm tra | Expected | Result |
|---|---|---|---|---|
| `CP_S01_ANNUAL_LEAVE` | Single | Chọn area nghỉ phép | `policy(leave)` | `[Chạy v3 group]` |
| `CP_S02_PASSWORD_RULE` | Single | Chọn area bảo mật CNTT | `policy(it_security)` | `[Chạy v3 group]` |
| `CP_S03_COMPARE_EXISTING_EVIDENCE` | Single | Tool mới với hai evidence có sẵn | `policy_compare` | `[Chạy v3 group]` |
| `CP_S04_CAPABILITY_NO_TOOL` | Single | Meta question không cần tool | no tool | `[Chạy v3 group]` |
| `CP_S05_AMBIGUOUS_POLICY` | Single | Thiếu policy context | `clarify(text)` | `[Chạy v3 group]` |
| `CP_M01_REMOTE_WORK_CARRYOVER` | Multi | Carry topic remote work | `policy(remote_work)` | `[Chạy v3 group]` |
| `CP_M02_LEAVE_CORRECTION` | Multi | Sửa nghỉ ốm thành phép năm | `policy(leave)` | `[Chạy v3 group]` |
| `CP_M03_SWITCH_TO_EQUIPMENT` | Multi | Đổi IT security sang equipment | `policy(equipment)` | `[Chạy v3 group]` |
| `CP_M04_CANCEL_LOOKUP` | Multi | Hủy yêu cầu | no tool | `[Chạy v3 group]` |
| `CP_M05_COMPARE_TWO_POLICIES` | Multi | So sánh evidence từ lượt trước | `policy_compare` | `[Chạy v3 group]` |

## B4. Live chat evidence

UI và CLI cùng dùng `run_model_tool_loop`; transcript được lưu trong
`transcripts/*.transcript.json`.

| Scenario | Version | Tool calls cần có | Transcript | Outcome |
|---|---|---|---|---|
| Tra cứu nghỉ phép | v3 | `policy(query, leave, top_k)` | `[Điền file]` | `[Điền]` |
| Thiếu policy rồi bổ sung | v3 | `clarify` → `policy` | `[Điền file]` | `[Điền]` |
| So sánh hai section | v3 | `policy` → `policy_compare` hoặc evidence supplied → compare | `[Điền file]` | `[Điền]` |
| External action | v3 | `clarify(yes_no)` | `[Điền file]` | `[Điền]` |

## B5. Tool capability evidence

| Category | Evidence | What worked | Risk / Guardrail |
|---|---|---|---|
| Must-have tool mới | `tools/policy_compare/tool.py`, `TOOL.md`, registry, schema | So sánh ≥2 section, giữ evidence IDs và nguồn | Không tự search; tension chỉ để manual review |
| Tool đề tài | `tools/policy/tool.py` | Đọc 10 file trong `internal-policies/`, tách cả heading cấp 2/3 | Không tìm thấy phải nói insufficient evidence |
| Mock data | `internal-policies/*.md` | Bao phủ 10 nhóm policy thường gặp | Dữ liệu giả lập, không phải tư vấn pháp lý |

## B6. Reflection

- Routing chung, multi-turn precedence, citation format và safety boundary thuộc
  `system_prompt.md`.
- Use/do-not-use, enum `policy_area`, required arguments và schema thuộc
  `tools.yaml`.
- Chuyển từ `company_policy/` sang `internal-policies/` là thay đổi
  implementation/data contract, không chỉ là prompt engineering.
- Routing PASS không chứng minh nội dung truy xuất đúng; `tool_results` và
  `source_path` cần được review thủ công.
- `policy_compare` không thay thế HR, IT, Finance hoặc quản lý có thẩm quyền.

## B7. Checklist trước khi nộp

- [ ] Điền họ tên và mã sinh viên của 5 thành viên.
- [ ] Điền public URL hoặc xác nhận demo local.
- [ ] Thêm OpenAI key vào `.env` cục bộ, không commit.
- [ ] Chạy v2/v3 base và group eval.
- [ ] Cập nhật metric/run file v2–v3 trong report và version log.
- [ ] Chat live ít nhất 3 scenario và lưu transcript.
- [ ] Kiểm tra `provider_error_cases=0`.
- [ ] Review mọi `tool_results` có error.
- [ ] Không nộp `.env`, `.venv`, API key hoặc cache.

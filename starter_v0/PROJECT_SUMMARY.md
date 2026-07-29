# TechNova Company Policy Assistant

## Mục tiêu

Tra cứu quy định nội bộ từ 10 tài liệu mock trong `internal-policies/` và trả
lời kèm bằng chứng: tên tài liệu, section và source path.

## Thành phần chính

- `tools/policy`: tìm section liên quan trong dữ liệu TechNova.
- `tools/policy_compare`: tool mới của nhóm để so sánh từ hai evidence trở lên.
- `artifacts/system_prompt.md`: routing, citation, clarification và guardrails.
- `data/eval_group.json`: đúng 10 case nhóm tự viết, gồm 5 single + 5 multi.
- `app.py`: UI Streamlit có chat, tool trace, policy library và version evidence.
- `artifacts/REPORT.md`: report A/B và bảng điền thông tin 5 thành viên.

## Chạy local

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Điền `OPENAI_API_KEY` trong `.env`, sau đó:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Mở `http://localhost:8501`.

## Chạy evidence v2–v3

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_policy_versions.ps1
```

Sau khi chạy, điền metric/run v2–v3 và transcript vào `artifacts/REPORT.md`.

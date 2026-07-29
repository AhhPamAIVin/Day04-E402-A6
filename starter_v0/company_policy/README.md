# Legacy Company Policy KB

> Thư mục này là dữ liệu mẫu ban đầu của starter và không còn là nguồn chính
> của đề tài. TechNova Company Policy Assistant hiện đọc dữ liệu từ
> `starter_v0/internal-policies/`.

This folder contains a small fake internal policy handbook for the lab.

The model does not read these files directly. It calls `search_company_policy(query, policy_area, top_k)`, then Python code searches these markdown files and returns selected sections with source metadata.

Policy areas:

- `ai_research`
- `source_citation`
- `data_privacy`
- `external_publishing`
- `tool_usage`

Use this for internal company rules. Use live tools for current news, tweets, URLs, and papers.

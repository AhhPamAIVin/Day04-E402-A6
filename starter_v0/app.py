from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

from chat import (
    ARTIFACTS_DIR,
    now_iso,
    run_model_tool_loop,
    safe_slug,
    trim_history,
    write_transcript,
)
from env_loader import load_lab_env
from providers import make_provider
from tools import load_tool_declarations, to_openai_tools
from versioning import artifact_version_dict, build_artifact_version


ROOT = Path(__file__).parent
POLICY_DIR = ROOT / "internal-policies"
RUNS_DIR = ROOT / "runs"
TRANSCRIPTS_DIR = ROOT / "transcripts"
SYSTEM_PROMPT_PATH = ARTIFACTS_DIR / "system_prompt.md"
TOOLS_PATH = ARTIFACTS_DIR / "tools.yaml"

load_lab_env(ROOT)

st.set_page_config(
    page_title="TechNova Policy Assistant",
    page_icon="📘",
    layout="wide",
)


def policy_title(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem


def new_transcript(version: str, model: str, rounds: int) -> tuple[Path, dict[str, Any]]:
    artifact = build_artifact_version(version, SYSTEM_PROMPT_PATH, TOOLS_PATH)
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
    transcript_id = "_".join([safe_slug(version), "openai", stamp])
    path = TRANSCRIPTS_DIR / f"{transcript_id}.transcript.json"
    payload: dict[str, Any] = {
        "transcript_id": transcript_id,
        **artifact_version_dict(artifact),
        "provider": "openai",
        "model": model,
        "system_prompt": str(SYSTEM_PROMPT_PATH),
        "tools": str(TOOLS_PATH),
        "policy_data": str(POLICY_DIR),
        "history_window": 5,
        "max_tool_rounds": rounds,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "turns": [],
    }
    return path, payload


def initialize_state(version: str, model: str, rounds: int) -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "turn_records" not in st.session_state:
        st.session_state.turn_records = []
    if "transcript" not in st.session_state:
        path, payload = new_transcript(version, model, rounds)
        st.session_state.transcript_path = path
        st.session_state.transcript = payload


def reset_chat(version: str, model: str, rounds: int) -> None:
    st.session_state.messages = []
    st.session_state.turn_records = []
    path, payload = new_transcript(version, model, rounds)
    st.session_state.transcript_path = path
    st.session_state.transcript = payload


def render_trace(turn: dict[str, Any]) -> None:
    events = turn.get("tool_events") or []
    if not events:
        st.caption("Không gọi tool.")
        return
    for index, event in enumerate(events, start=1):
        result = event.get("result")
        has_error = isinstance(result, dict) and bool(result.get("error"))
        status = "error" if has_error else "ok"
        with st.expander(
            f"{index}. {event.get('tool', 'unknown')} · {status}",
            expanded=True,
        ):
            args_col, result_col = st.columns(2)
            with args_col:
                st.markdown("**Arguments**")
                st.json(event.get("args") or {})
            with result_col:
                st.markdown("**Result / Evidence**")
                st.json(result)


def run_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not RUNS_DIR.exists():
        return rows
    for path in sorted(RUNS_DIR.glob("*.json"), reverse=True):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        summary = payload.get("summary", {})
        rows.append({
            "version": payload.get("version"),
            "suite": payload.get("suite"),
            "case accuracy": summary.get("case_accuracy"),
            "routing": summary.get("tool_routing_accuracy"),
            "arguments": summary.get("argument_accuracy"),
            "multi-turn": summary.get("multiturn_accuracy"),
            "provider errors": summary.get("provider_error_cases"),
            "file": path.name,
        })
    return rows


st.markdown(
    """
    <style>
      .block-container {padding-top: 1.8rem; padding-bottom: 3rem;}
      [data-testid="stMetricValue"] {font-size: 1.45rem;}
      .policy-hero {
        border: 1px solid #dbe4ea; border-radius: 18px; padding: 24px 28px;
        background: linear-gradient(135deg, #f8fbfd 0%, #eef7f4 100%);
        margin-bottom: 18px;
      }
      .policy-hero h1 {margin: 0 0 8px 0; color: #173b3f;}
      .policy-hero p {margin: 0; color: #51666a;}
    </style>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Phiên làm việc")
    version = st.text_input("Artifact version", value="v3")
    model = st.text_input("OpenAI model", value="gpt-4o-mini")
    max_rounds = st.slider("Số vòng tool tối đa", 1, 6, 4)
    key_ready = bool(os.getenv("OPENAI_API_KEY"))
    if key_ready:
        st.success("OpenAI đã cấu hình")
    else:
        st.error("Chưa có OPENAI_API_KEY trong .env")
    if st.button("Tạo phiên mới", use_container_width=True):
        reset_chat(version, model, max_rounds)
        st.rerun()
    st.divider()
    st.caption("API key không được hiển thị hoặc ghi vào transcript.")

initialize_state(version, model, max_rounds)
artifact = build_artifact_version(version, SYSTEM_PROMPT_PATH, TOOLS_PATH)
policy_files = sorted(POLICY_DIR.glob("*.md"))

st.markdown(
    """
    <div class="policy-hero">
      <h1>TechNova Policy Assistant</h1>
      <p>Tra cứu quy định nội bộ và trả lời kèm section, nguồn bằng chứng và tool trace.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

chat_tab, library_tab, evidence_tab, demo_tab = st.tabs([
    "Hỏi đáp",
    "Kho chính sách",
    "Evidence v0–v3",
    "Kịch bản demo",
])

with chat_tab:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Policy documents", len(policy_files))
    m2.metric("Declared tools", len(load_tool_declarations(TOOLS_PATH)))
    m3.metric("Provider", "OpenAI")
    m4.metric("Version", version)
    st.caption(
        f"artifact={artifact.artifact_version} · "
        f"prompt={artifact.prompt_hash[:10]} · tools={artifact.tools_hash[:10]}"
    )

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant" and message.get("record_index") is not None:
                record_index = message["record_index"]
                if record_index < len(st.session_state.turn_records):
                    render_trace(st.session_state.turn_records[record_index])

    prompt = st.chat_input("Ví dụ: Nhân viên có bao nhiêu ngày nghỉ phép năm?")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        turn: dict[str, Any] = {
            "turn_index": len(st.session_state.turn_records) + 1,
            "started_at": now_iso(),
            "user": prompt,
            "status": "started",
            "assistant_text": None,
            "rounds": [],
            "tool_events": [],
        }
        with st.chat_message("assistant"):
            if not key_ready:
                result = {
                    "status": "configuration_error",
                    "assistant_text": "Hãy điền OPENAI_API_KEY trong file .env rồi thử lại.",
                    "rounds": [],
                    "tool_events": [],
                }
            else:
                try:
                    system_prompt = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
                    declarations = load_tool_declarations(TOOLS_PATH)
                    tools = to_openai_tools(declarations)
                    history = [
                        {"role": item["role"], "content": item["content"]}
                        for item in st.session_state.messages[:-1]
                    ]
                    result = run_model_tool_loop(
                        provider=make_provider("openai"),
                        messages=[
                            {"role": "system", "content": system_prompt},
                            *trim_history(history, 5),
                            {"role": "user", "content": prompt},
                        ],
                        tools=tools,
                        model=model,
                        max_tool_rounds=max_rounds,
                    )
                except Exception as exc:
                    result = {
                        "status": "provider_error",
                        "assistant_text": f"OpenAI request failed: {type(exc).__name__}: {exc}",
                        "rounds": [],
                        "tool_events": [],
                    }

            answer = result.get("assistant_text") or "Không có phản hồi."
            st.markdown(answer)
            turn.update(result)
            render_trace(turn)

        turn["ended_at"] = now_iso()
        record_index = len(st.session_state.turn_records)
        st.session_state.turn_records.append(turn)
        st.session_state.messages.append({
            "role": "assistant",
            "content": answer,
            "record_index": record_index,
        })
        st.session_state.transcript["turns"].append(turn)
        write_transcript(st.session_state.transcript_path, st.session_state.transcript)

with library_tab:
    st.subheader("10 tài liệu nội bộ của TechNova Solutions")
    st.caption("Đây là mock data chính mà tool policy đang đọc.")
    for path in policy_files:
        with st.expander(policy_title(path)):
            st.code(f"internal-policies/{path.name}", language=None)
            headings = [
                line.lstrip("#").strip()
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.startswith("### ")
            ]
            if headings:
                st.markdown("\n".join(f"- {heading}" for heading in headings))

with evidence_tab:
    st.subheader("Bảng run evidence")
    rows = run_rows()
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info("Chưa có run JSON.")
    st.subheader("Transcript hiện tại")
    st.json({
        **artifact_version_dict(artifact),
        "transcript": st.session_state.transcript_path.name,
        "turns": len(st.session_state.turn_records),
    })

with demo_tab:
    st.subheader("5 câu hỏi demo")
    st.markdown(
        """
1. **Nghỉ phép:** Nhân viên làm trên 5 năm có bao nhiêu ngày nghỉ phép năm?
2. **Bảo mật:** Mật khẩu phải dài bao nhiêu ký tự và đổi sau bao lâu?
3. **Remote:** Một tuần được làm từ xa tối đa mấy ngày và cần duyệt trước bao lâu?
4. **Chi phí:** Công ty hoàn tối đa bao nhiêu tiền khách sạn mỗi đêm?
5. **So sánh:** So sánh quy định dùng thiết bị cá nhân trong Data Privacy và IT Security.

Khi demo, mở trace để chỉ ra `policy_area`, section, `source_path`, result/error và artifact version.
        """
    )

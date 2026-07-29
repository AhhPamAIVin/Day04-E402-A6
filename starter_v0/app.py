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

SUGGESTED_QUESTIONS = [
    ("🌿", "Nghỉ phép", "Nhân viên làm trên 5 năm có bao nhiêu ngày nghỉ phép năm?"),
    ("🔐", "Bảo mật", "Mật khẩu công ty phải dài bao nhiêu ký tự và đổi bao lâu một lần?"),
    ("🏠", "Làm từ xa", "Một tuần được remote tối đa mấy ngày và cần duyệt trước bao lâu?"),
    ("🧾", "Công tác phí", "Công ty hoàn tối đa bao nhiêu tiền khách sạn mỗi đêm?"),
]

load_lab_env(ROOT)

st.set_page_config(
    page_title="TechNova Policy Assistant",
    page_icon="📘",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Community Cloud stores deployment credentials in Streamlit Secrets instead
# of a local .env file. Root-level secrets use the same provider code.
if not os.getenv("OPENAI_API_KEY"):
    try:
        cloud_openai_key = str(st.secrets["OPENAI_API_KEY"]).strip()
        if cloud_openai_key:
            os.environ["OPENAI_API_KEY"] = cloud_openai_key
    except (KeyError, FileNotFoundError):
        pass


def policy_title(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem


def policy_headings(path: Path) -> list[str]:
    return [
        line.lstrip("#").strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("### ")
    ]


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


def render_policy_evidence(result: dict[str, Any]) -> None:
    results = result.get("results") or []
    if not results:
        st.warning("Không tìm thấy section phù hợp trong kho chính sách.")
        return
    st.markdown(f"**{len(results)} bằng chứng được truy xuất**")
    for item in results:
        title = item.get("title") or item.get("doc_id") or "Policy document"
        section = item.get("section") or "Không rõ section"
        st.markdown(f"**{title}** · `{section}`")
        if item.get("facts"):
            st.markdown(f"> {item['facts']}")
        source = item.get("source_path") or item.get("source") or "Không rõ nguồn"
        score = item.get("score")
        score_text = f" · relevance {score}" if score is not None else ""
        st.caption(f"📎 {source}{score_text}")


def render_compare_evidence(result: dict[str, Any]) -> None:
    summary_col, source_col = st.columns([1.2, 1])
    with summary_col:
        st.markdown("**Kết quả tổng hợp**")
        st.write(f"{result.get('section_count', 0)} policy section được so sánh")
        requirements = result.get("combined_requirements") or []
        if requirements:
            st.caption(f"{len(requirements)} yêu cầu/điều cấm được nhận diện")
        tensions = result.get("possible_tensions") or []
        if tensions:
            st.warning(f"{len(tensions)} điểm cần con người review")
        else:
            st.success("Không phát hiện tension theo heuristic")
    with source_col:
        st.markdown("**Nguồn bằng chứng**")
        for source in result.get("sources") or []:
            label = source.get("source_path") or source.get("source") or "Unknown"
            st.caption(f"{source.get('evidence_id', '•')} · {label}")


def render_trace(turn: dict[str, Any]) -> None:
    events = turn.get("tool_events") or []
    if not events:
        st.caption("✓ Trả lời trực tiếp — không cần gọi công cụ")
        return

    st.markdown('<div class="trace-label">DẤU VẾT XỬ LÝ</div>', unsafe_allow_html=True)
    for index, event in enumerate(events, start=1):
        result = event.get("result")
        has_error = isinstance(result, dict) and bool(result.get("error"))
        icon = "⚠️" if has_error else "✓"
        status = "Lỗi" if has_error else "Hoàn tất"
        tool_name = event.get("tool", "unknown")
        with st.expander(
            f"{icon} Bước {index} · {tool_name} · {status}",
            expanded=tool_name in {"policy", "policy_compare"} or has_error,
        ):
            args = event.get("args") or {}
            if args:
                chips = " · ".join(f"**{key}:** `{value}`" for key, value in args.items() if not isinstance(value, (list, dict)))
                if chips:
                    st.markdown(chips)
            if isinstance(result, dict):
                if result.get("error"):
                    st.error(result.get("message") or result["error"])
                elif tool_name == "policy":
                    render_policy_evidence(result)
                elif tool_name == "policy_compare":
                    render_compare_evidence(result)
                else:
                    st.success("Công cụ đã thực thi thành công.")
            with st.popover("Xem JSON kỹ thuật"):
                st.markdown("**Arguments**")
                st.json(args)
                st.markdown("**Result**")
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
            "Version": payload.get("version"),
            "Suite": payload.get("suite"),
            "Case accuracy": summary.get("case_accuracy"),
            "Routing": summary.get("tool_routing_accuracy"),
            "Arguments": summary.get("argument_accuracy"),
            "Multi-turn": summary.get("multiturn_accuracy"),
            "Provider errors": summary.get("provider_error_cases"),
            "Run file": path.name,
        })
    return rows


def execute_prompt(
    prompt: str,
    *,
    key_ready: bool,
    model: str,
    max_rounds: int,
) -> None:
    st.session_state.messages.append({"role": "user", "content": prompt})
    turn: dict[str, Any] = {
        "turn_index": len(st.session_state.turn_records) + 1,
        "started_at": now_iso(),
        "user": prompt,
        "status": "started",
        "assistant_text": None,
        "rounds": [],
        "tool_events": [],
    }

    if not key_ready:
        result = {
            "status": "configuration_error",
            "assistant_text": (
                "Chưa có OpenAI key. Khi chạy local, thêm key vào `.env`; "
                "khi deploy, thêm `OPENAI_API_KEY` trong Streamlit Secrets."
            ),
            "rounds": [],
            "tool_events": [],
        }
    else:
        try:
            declarations = load_tool_declarations(TOOLS_PATH)
            history = [
                {"role": item["role"], "content": item["content"]}
                for item in st.session_state.messages[:-1]
            ]
            result = run_model_tool_loop(
                provider=make_provider("openai"),
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT_PATH.read_text(encoding="utf-8"),
                    },
                    *trim_history(history, 5),
                    {"role": "user", "content": prompt},
                ],
                tools=to_openai_tools(declarations),
                model=model,
                max_tool_rounds=max_rounds,
            )
        except Exception as exc:
            result = {
                "status": "provider_error",
                "assistant_text": f"Không thể hoàn tất yêu cầu: {type(exc).__name__}: {exc}",
                "rounds": [],
                "tool_events": [],
            }

    answer = result.get("assistant_text") or "Không có phản hồi."
    turn.update(result)
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


st.markdown(
    """
    <style>
      :root {
        --ink: #153438;
        --muted: #617579;
        --teal: #0f766e;
        --teal-dark: #115e59;
        --mint: #e7f5f1;
        --cream: #fbfaf6;
        --line: #dce7e4;
        --coral: #e76f51;
      }
      .stApp {
        background:
          radial-gradient(circle at 85% 4%, rgba(15,118,110,.08), transparent 26rem),
          linear-gradient(180deg, #f9fbfa 0%, #ffffff 34rem);
        color: var(--ink);
      }
      .block-container {max-width: 1240px; padding-top: 1.4rem; padding-bottom: 4rem;}
      [data-testid="stSidebar"] {background: #f4f8f7; border-right: 1px solid var(--line);}
      [data-testid="stSidebar"] .block-container {padding-top: 1.6rem;}
      [data-testid="stMetric"] {
        background: rgba(255,255,255,.82); border: 1px solid var(--line);
        border-radius: 14px; padding: 12px 16px;
      }
      [data-testid="stMetricValue"] {font-size: 1.35rem; color: var(--ink);}
      [data-testid="stChatMessage"] {
        border: 1px solid #e6eeec; border-radius: 18px;
        padding: 8px 12px; background: rgba(255,255,255,.84);
        margin-bottom: 12px;
      }
      [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
        background: #edf7f4; border-color: #d4e9e3;
      }
      [data-testid="stChatInput"] {border-radius: 16px; border-color: #bfd7d1;}
      .stButton > button {
        border-radius: 12px; border: 1px solid #cfe0dc; min-height: 44px;
        transition: transform .12s ease, border-color .12s ease;
      }
      .stButton > button:hover {transform: translateY(-1px); border-color: var(--teal);}
      div[data-testid="stExpander"] {border: 1px solid var(--line); border-radius: 12px;}
      .hero {
        display: flex; justify-content: space-between; align-items: flex-end; gap: 24px;
        padding: 30px 34px; margin-bottom: 18px; border-radius: 24px;
        background: linear-gradient(125deg, #123f42 0%, #0f766e 68%, #18877d 100%);
        box-shadow: 0 18px 50px rgba(15, 76, 72, .16); color: white;
      }
      .hero-kicker {font-size: .76rem; letter-spacing: .15em; font-weight: 700; opacity: .78;}
      .hero h1 {font-size: clamp(2rem, 5vw, 3.15rem); line-height: 1.02; margin: 9px 0 10px;}
      .hero p {font-size: 1.02rem; line-height: 1.6; max-width: 680px; margin: 0; opacity: .88;}
      .hero-badge {
        white-space: nowrap; background: rgba(255,255,255,.12);
        border: 1px solid rgba(255,255,255,.28); border-radius: 999px;
        padding: 9px 14px; font-size: .82rem;
      }
      .section-title {font-size: 1.05rem; font-weight: 700; color: var(--ink); margin: 14px 0 4px;}
      .eyebrow {font-size: .73rem; letter-spacing: .12em; font-weight: 750; color: var(--teal);}
      .empty-state {
        border: 1px dashed #bcd4ce; border-radius: 18px; padding: 24px;
        background: rgba(242,249,247,.7); margin: 16px 0;
      }
      .empty-state h3 {margin: 0 0 6px; color: var(--ink);}
      .empty-state p {margin: 0; color: var(--muted);}
      .trace-label {font-size: .68rem; letter-spacing: .12em; font-weight: 750; color: var(--teal); margin: 16px 0 6px;}
      .sidebar-brand {
        background: #123f42; color: white; border-radius: 16px;
        padding: 16px 18px; margin-bottom: 18px;
      }
      .sidebar-brand strong {font-size: 1.05rem;}
      .sidebar-brand span {display: block; opacity: .68; font-size: .78rem; margin-top: 3px;}
      .status-dot {display:inline-block; width:8px; height:8px; border-radius:50%; background:#55c59f; margin-right:6px;}
      .doc-card {
        border: 1px solid var(--line); border-radius: 16px; background: #fff;
        padding: 18px; min-height: 145px; margin-bottom: 14px;
      }
      .doc-card .doc-index {font-size: .72rem; color: var(--teal); font-weight: 750; letter-spacing: .08em;}
      .doc-card h4 {font-size: 1rem; margin: 8px 0; color: var(--ink);}
      .doc-card p {font-size: .83rem; color: var(--muted); margin: 0;}
      @media (max-width: 760px) {
        .block-container {padding-left: 1rem; padding-right: 1rem;}
        .hero {padding: 24px; align-items: flex-start; flex-direction: column;}
        .hero h1 {font-size: 2.15rem;}
      }
    </style>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown(
        """
        <div class="sidebar-brand">
          <strong>📘 TechNova Policy</strong>
          <span>Evidence-first internal assistant</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div class="eyebrow">CẤU HÌNH PHIÊN</div>', unsafe_allow_html=True)
    version = st.selectbox("Artifact version", ["v3", "v2", "v1", "v0"], index=0)
    model = st.text_input("OpenAI model", value="gpt-4o-mini")
    max_rounds = st.slider("Số vòng xử lý tối đa", 1, 6, 4)
    key_ready = bool(os.getenv("OPENAI_API_KEY"))
    if key_ready:
        st.success("● OpenAI sẵn sàng")
    else:
        st.warning("● Chưa cấu hình OpenAI key")
    if st.button("＋ Cuộc hội thoại mới", use_container_width=True, type="primary"):
        reset_chat(version, model, max_rounds)
        st.rerun()
    st.divider()
    st.caption("🔒 Key không xuất hiện trong giao diện hoặc transcript.")

initialize_state(version, model, max_rounds)
artifact = build_artifact_version(version, SYSTEM_PROMPT_PATH, TOOLS_PATH)
policy_files = sorted(POLICY_DIR.glob("*.md"))

st.markdown(
    f"""
    <section class="hero">
      <div>
        <div class="hero-kicker">TECHNOVA · INTERNAL POLICY</div>
        <h1>Hỏi chính sách.<br/>Nhận câu trả lời có căn cứ.</h1>
        <p>Tra cứu 10 tài liệu nội bộ, xem bằng chứng theo section và theo dõi từng công cụ mà agent đã sử dụng.</p>
      </div>
      <div class="hero-badge"><span class="status-dot"></span>{len(policy_files)} tài liệu đã lập chỉ mục</div>
    </section>
    """,
    unsafe_allow_html=True,
)

chat_tab, library_tab, evidence_tab, demo_tab = st.tabs([
    "💬 Hỏi đáp",
    "📚 Kho chính sách",
    "📊 Evidence",
    "🎬 Demo",
])

with chat_tab:
    st.markdown('<div class="section-title">Bắt đầu với một câu hỏi mẫu</div>', unsafe_allow_html=True)
    suggestion_columns = st.columns(4)
    selected_prompt: str | None = None
    for column, (icon, label, question) in zip(suggestion_columns, SUGGESTED_QUESTIONS):
        with column:
            if st.button(f"{icon} {label}", key=f"suggest_{label}", use_container_width=True):
                selected_prompt = question

    if not st.session_state.messages:
        st.markdown(
            """
            <div class="empty-state">
              <h3>Tôi có thể giúp bạn tìm quy định nào?</h3>
              <p>Hỏi bằng ngôn ngữ tự nhiên. Câu trả lời sẽ kèm section và đường dẫn tài liệu để bạn tự kiểm chứng.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant" and message.get("record_index") is not None:
                record_index = message["record_index"]
                if record_index < len(st.session_state.turn_records):
                    render_trace(st.session_state.turn_records[record_index])

    typed_prompt = st.chat_input("Hỏi về nghỉ phép, remote, bảo mật, chi phí, thiết bị…")
    prompt = typed_prompt or selected_prompt
    if prompt:
        with st.spinner("Đang tra cứu policy và kiểm tra nguồn…"):
            execute_prompt(
                prompt,
                key_ready=key_ready,
                model=model,
                max_rounds=max_rounds,
            )
        st.rerun()

with library_tab:
    heading_col, count_col = st.columns([4, 1])
    with heading_col:
        st.subheader("Kho chính sách TechNova")
        st.caption("Tìm nhanh tài liệu và các mục quy định cốt lõi.")
    with count_col:
        st.metric("Tài liệu", len(policy_files))

    library_query = st.text_input(
        "Tìm trong danh mục",
        placeholder="Ví dụ: nghỉ phép, mật khẩu, thiết bị…",
        label_visibility="collapsed",
    ).strip().lower()
    filtered_files = [
        path for path in policy_files
        if not library_query
        or library_query in policy_title(path).lower()
        or any(library_query in heading.lower() for heading in policy_headings(path))
    ]
    if not filtered_files:
        st.info("Không có tài liệu phù hợp với từ khóa này.")
    for row_start in range(0, len(filtered_files), 2):
        columns = st.columns(2)
        for column, path in zip(columns, filtered_files[row_start:row_start + 2]):
            headings = policy_headings(path)
            with column:
                st.markdown(
                    f"""
                    <article class="doc-card">
                      <div class="doc-index">{path.stem.split('_', 1)[0]} · POLICY DOCUMENT</div>
                      <h4>{policy_title(path)}</h4>
                      <p>{' · '.join(headings[:3]) if headings else 'Tài liệu nội bộ TechNova'}</p>
                    </article>
                    """,
                    unsafe_allow_html=True,
                )
                with st.expander("Xem mục và đường dẫn"):
                    st.code(f"internal-policies/{path.name}", language=None)
                    if headings:
                        st.markdown("\n".join(f"- {heading}" for heading in headings))

with evidence_tab:
    rows = run_rows()
    st.subheader("Bằng chứng cải tiến qua các version")
    st.caption("Metric được đọc trực tiếp từ run JSON; provider error phải bằng 0.")
    if rows:
        latest = rows[0]
        metric_columns = st.columns(4)
        metric_columns[0].metric("Latest version", latest["Version"] or "—")
        metric_columns[1].metric("Case accuracy", latest["Case accuracy"] if latest["Case accuracy"] is not None else "—")
        metric_columns[2].metric("Routing", latest["Routing"] if latest["Routing"] is not None else "—")
        metric_columns[3].metric("Provider errors", latest["Provider errors"] if latest["Provider errors"] is not None else "—")
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info("Chưa có run JSON để hiển thị.")

    session_col, artifact_col = st.columns(2)
    with session_col:
        st.markdown("**Phiên hiện tại**")
        st.write(f"{len(st.session_state.turn_records)} lượt đã xử lý")
        transcript_bytes = json.dumps(
            st.session_state.transcript,
            ensure_ascii=False,
            indent=2,
            default=str,
        ).encode("utf-8")
        st.download_button(
            "Tải transcript JSON",
            data=transcript_bytes,
            file_name=st.session_state.transcript_path.name,
            mime="application/json",
            use_container_width=True,
        )
    with artifact_col:
        st.markdown("**Artifact identity**")
        st.code(
            f"{artifact.artifact_version}\n"
            f"prompt {artifact.prompt_hash[:12]}\n"
            f"tools  {artifact.tools_hash[:12]}",
            language=None,
        )

with demo_tab:
    st.subheader("Kịch bản trình bày 5 phút")
    demo_items = [
        ("01", "Tra cứu chính xác", "Hỏi số ngày nghỉ phép của nhân viên trên 5 năm.", "`policy(area=leave)` + nguồn"),
        ("02", "Kiểm tra bảo mật", "Hỏi độ dài và chu kỳ đổi mật khẩu.", "`policy(area=it_security)`"),
        ("03", "Hội thoại nhiều lượt", "Đổi từ mật khẩu sang thời hạn báo mất laptop.", "Latest correction → `equipment`"),
        ("04", "Không đoán dữ liệu", "Hỏi “quy định đó áp dụng thế nào?”.", "`clarify(text)`"),
        ("05", "Tool mới của nhóm", "So sánh Data Privacy với IT Security.", "`policy_compare` + evidence IDs"),
    ]
    for number, title, prompt_text, evidence in demo_items:
        left, middle, right = st.columns([0.45, 2.5, 1.4])
        left.markdown(f"### {number}")
        middle.markdown(f"**{title}**  \n{prompt_text}")
        right.markdown(evidence)
        st.divider()

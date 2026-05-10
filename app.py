import html
import os
import time

import streamlit as st

from agents import run_research


st.set_page_config(
    page_title="Research Assistant",
    page_icon="RA",
    layout="wide",
)


LOGO_OPTIONS = {
    "Monogram": "RA",
    "Capsule": "AI",
    "Research": "R",
    "Minimal": "A",
}


def load_env_file(path: str = ".env", override: bool = False) -> dict[str, str]:
    loaded: dict[str, str] = {}
    if not os.path.exists(path):
        return loaded

    with open(path, "r", encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            clean_key = key.strip()
            clean_value = value.strip().strip('"').strip("'")
            loaded[clean_key] = clean_value
            if override:
                os.environ[clean_key] = clean_value
            else:
                os.environ.setdefault(clean_key, clean_value)

    return loaded


load_env_file()

if "groq_api_key" not in st.session_state:
    st.session_state.groq_api_key = os.getenv("GROQ_API_KEY", "")
if "tavily_api_key" not in st.session_state:
    st.session_state.tavily_api_key = os.getenv("TAVILY_API_KEY", "")
if "alt_groq_api_key" not in st.session_state:
    st.session_state.alt_groq_api_key = ""
if "alt_tavily_api_key" not in st.session_state:
    st.session_state.alt_tavily_api_key = ""


with st.sidebar:
    st.title("Control")
    st.caption("Press Ctrl+B to show or hide this control panel.")
    dark_mode = st.toggle("Dark mode", value=False)
    logo_choice = st.selectbox("Logo", list(LOGO_OPTIONS.keys()), index=0)

    st.divider()
    st.subheader("API keys")
    if st.button("Load keys from .env", use_container_width=True):
        loaded_keys = load_env_file(override=True)
        st.session_state.groq_api_key = loaded_keys.get(
            "GROQ_API_KEY",
            os.getenv("GROQ_API_KEY", ""),
        )
        st.session_state.tavily_api_key = loaded_keys.get(
            "TAVILY_API_KEY",
            os.getenv("TAVILY_API_KEY", ""),
        )
        st.success("API keys loaded from .env.")

    use_alternative_keys = st.toggle("Use alternative keys", value=False)

    primary_groq_key = st.text_input(
        "Groq API key",
        type="password",
        key="groq_api_key",
        placeholder="gsk_...",
    )
    primary_tavily_key = st.text_input(
        "Tavily API key",
        type="password",
        key="tavily_api_key",
        placeholder="tvly-...",
    )

    with st.expander("Alternative API keys"):
        alt_groq_key = st.text_input(
            "Alternative Groq API key",
            type="password",
            key="alt_groq_api_key",
            placeholder="gsk_...",
        )
        alt_tavily_key = st.text_input(
            "Alternative Tavily API key",
            type="password",
            key="alt_tavily_api_key",
            placeholder="tvly-...",
        )

    groq_key = alt_groq_key if use_alternative_keys else primary_groq_key
    tavily_key = alt_tavily_key if use_alternative_keys else primary_tavily_key
    active_key_set = "alternative" if use_alternative_keys else "primary"
    st.caption(
        f"Active: {active_key_set} | "
        f"Groq {'loaded' if groq_key else 'missing'} | "
        f"Tavily {'loaded' if tavily_key else 'missing'}"
    )

    st.divider()
    st.subheader("Report")
    source_count = st.slider("Sources", min_value=3, max_value=8, value=5, step=1)
    report_length = st.radio(
        "Length",
        options=["Brief", "Standard", "Detailed"],
        index=1,
        horizontal=True,
    )
    tone = st.radio(
        "Tone",
        options=["Neutral", "Executive", "Technical"],
        index=0,
        horizontal=True,
    )
    include_citations = st.toggle("Include citations", value=True)


theme_class = "theme-dark" if dark_mode else "theme-light"
logo_text = LOGO_OPTIONS[logo_choice]

if dark_mode:
    colors = {
        "bg": "#111111",
        "surface": "#1a1a1a",
        "surface_2": "#242424",
        "text": "#f4efe6",
        "muted": "#bcb4a5",
        "border": "#f4efe6",
        "accent": "#ff6b6b",
        "accent_2": "#7ab7ff",
        "accent_3": "#52d187",
        "shadow": "#f4efe6",
        "sidebar": "#171717",
        "active": "#3a2c12",
        "done": "#17351f",
        "dot": "rgba(255,255,255,0.08)",
    }
else:
    colors = {
        "bg": "#eee7d8",
        "surface": "#f8f2e5",
        "surface_2": "#fffaf0",
        "text": "#111111",
        "muted": "#5e5a51",
        "border": "#111111",
        "accent": "#ff595e",
        "accent_2": "#2f80ed",
        "accent_3": "#22a06b",
        "shadow": "#111111",
        "sidebar": "#eadfc9",
        "active": "#ffe1a8",
        "done": "#d8f5df",
        "dot": "rgba(0,0,0,0.09)",
    }


st.markdown(
    f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500;600;700&family=EB+Garamond:wght@400;500;600;700&display=swap');

    :root {{
        --font: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text",
            "Inter", "Segoe UI", sans-serif;
        --report-font: "EB Garamond", "Cormorant Garamond", Garamond, Georgia, serif;
    }}

    html, body, [class*="css"] {{
        font-family: var(--font) !important;
    }}

    [data-testid="stHeader"] {{
        display: none;
    }}

    .stApp {{
        --bg: {colors["bg"]};
        --surface: {colors["surface"]};
        --surface-2: {colors["surface_2"]};
        --text: {colors["text"]};
        --muted: {colors["muted"]};
        --border: {colors["border"]};
        --accent: {colors["accent"]};
        --accent-2: {colors["accent_2"]};
        --accent-3: {colors["accent_3"]};
        --shadow: {colors["shadow"]};
        --sidebar: {colors["sidebar"]};
        --active-card: {colors["active"]};
        --done-card: {colors["done"]};
        background:
            radial-gradient(circle at 1px 1px, {colors["dot"]} 1px, transparent 0),
            var(--bg);
        background-size: 14px 14px;
        color: var(--text);
    }}

    [data-testid="stSidebar"] {{
        background: var(--sidebar) !important;
        border-right: 2px solid var(--border);
    }}

    [data-testid="stSidebar"] * {{
        color: var(--text) !important;
    }}

    .block-container {{
        max-width: 1120px;
        padding: 3rem 2rem 4rem;
    }}

    .app-shell {{
        background: var(--surface);
        border: 2px solid var(--border);
        border-radius: 0 !important;
        box-shadow: 6px 6px 0 var(--shadow);
        color: var(--text);
        margin-bottom: 1rem;
    }}

    .topbar {{
        align-items: center;
        display: flex;
        gap: 1.5rem;
        justify-content: space-between;
        padding: 1.05rem 1.4rem;
    }}

    .brand {{
        align-items: center;
        display: flex;
        gap: 0.65rem;
        min-width: 150px;
    }}

    .logo {{
        align-items: center;
        background: var(--accent-2);
        border: 2px solid var(--border);
        border-radius: 14px;
        box-shadow: 3px 3px 0 var(--shadow);
        color: #ffffff;
        display: inline-flex;
        font-size: 0.9rem;
        font-weight: 800;
        height: 42px;
        justify-content: center;
        letter-spacing: -0.03em;
        width: 42px;
    }}

    .brand-name {{
        font-size: 0.9rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        line-height: 0.95;
        text-transform: uppercase;
    }}

    .nav {{
        align-items: center;
        display: flex;
        gap: 2rem;
        justify-content: center;
    }}

    .nav span {{
        color: var(--text);
        font-size: 0.82rem;
        font-weight: 700;
    }}

    .nav .active {{
        color: var(--accent);
    }}

    .mode-pill {{
        background: var(--surface-2);
        border: 2px solid var(--border);
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 800;
        padding: 0.45rem 0.75rem;
    }}

    .content {{
        padding: 0;
    }}

    .hero {{
        margin: 0 auto 1.15rem;
        max-width: 760px;
        text-align: center;
    }}

    .hero h1 {{
        color: var(--text);
        font-size: clamp(2.35rem, 5vw, 4.15rem);
        font-weight: 850;
        letter-spacing: -0.04em;
        line-height: 0.98;
        margin: 0 0 0.85rem;
    }}

    .hero p {{
        color: var(--text);
        font-size: 0.98rem;
        font-weight: 500;
        line-height: 1.45;
        margin: 0 auto;
        max-width: 500px;
    }}

    .stTextInput label {{
        color: var(--text) !important;
        font-size: 0.8rem !important;
        font-weight: 800 !important;
    }}

    .stTextInput input {{
        background: var(--surface-2) !important;
        border: 2px solid var(--border) !important;
        border-radius: 0 !important;
        box-shadow: 3px 3px 0 var(--shadow) !important;
        color: var(--text) !important;
        font-family: var(--font) !important;
        font-size: 0.95rem !important;
        font-weight: 600 !important;
        min-height: 3.15rem;
        padding: 0.75rem 0.9rem !important;
    }}

    .stTextInput input:focus {{
        border-color: var(--accent-2) !important;
        box-shadow: 3px 3px 0 var(--shadow), 0 0 0 3px rgba(47,128,237,0.18) !important;
    }}

    .stButton > button,
    .stDownloadButton > button {{
        background: var(--accent) !important;
        border: 2px solid var(--border) !important;
        border-radius: 0 !important;
        box-shadow: 3px 3px 0 var(--shadow) !important;
        color: #ffffff !important;
        font-family: var(--font) !important;
        font-size: 0.9rem !important;
        font-weight: 850 !important;
        min-height: 3.15rem;
        padding: 0.65rem 1rem !important;
        transition: transform 120ms ease, box-shadow 120ms ease;
        width: 100%;
    }}

    .stButton > button:hover,
    .stDownloadButton > button:hover {{
        box-shadow: 1px 1px 0 var(--shadow) !important;
        transform: translate(2px, 2px);
    }}

    .meta-grid {{
        display: grid;
        gap: 1rem;
        grid-template-columns: 0.72fr 1.28fr;
        margin-top: 1.4rem;
    }}

    .panel {{
        background: var(--surface-2);
        border: 2px solid var(--border);
        box-shadow: 4px 4px 0 var(--shadow);
        padding: 1rem;
    }}

    .panel h3 {{
        color: var(--text);
        font-size: 1rem;
        font-weight: 850;
        letter-spacing: -0.02em;
        margin: 0 0 0.8rem;
    }}

    .filters {{
        display: grid;
        gap: 0.6rem;
    }}

    .filter-line {{
        align-items: center;
        display: flex;
        gap: 0.5rem;
        color: var(--text);
        font-size: 0.86rem;
        font-weight: 700;
    }}

    .box {{
        border: 2px solid var(--border);
        height: 13px;
        width: 13px;
    }}

    .box.on {{
        background: var(--accent);
    }}

    .setting-value {{
        margin-left: auto;
        text-align: right;
    }}

    .pipeline-title {{
        align-items: baseline;
        display: flex;
        gap: 0.75rem;
        justify-content: center;
        margin-bottom: 0.85rem;
    }}

    .pipeline-title h2 {{
        color: var(--text);
        font-size: 1.15rem;
        font-weight: 850;
        letter-spacing: -0.02em;
        margin: 0;
    }}

    .pipeline-title span {{
        background: var(--surface-2);
        border: 2px solid var(--border);
        color: var(--text);
        font-size: 0.78rem;
        font-weight: 800;
        padding: 0.28rem 0.55rem;
    }}

    .agent-card {{
        background: var(--surface-2);
        border: 2px solid var(--border);
        box-shadow: 4px 4px 0 var(--shadow);
        margin-bottom: 0.85rem;
        padding: 0.95rem 1rem;
    }}

    .agent-card.active {{
        background: var(--active-card);
    }}

    .agent-card.done {{
        background: var(--done-card);
    }}

    .agent-label {{
        color: var(--muted);
        font-size: 0.72rem;
        font-weight: 850;
        letter-spacing: 0.08em;
        margin-bottom: 0.25rem;
        text-transform: uppercase;
    }}

    .agent-name {{
        color: var(--text);
        font-size: 0.98rem;
        font-weight: 800;
    }}

    .report-box {{
        background: var(--surface-2);
        border: 2px solid var(--border);
        box-shadow: 5px 5px 0 var(--shadow);
        color: var(--text);
        font-family: var(--report-font);
        font-size: 1.12rem;
        font-weight: 400;
        line-height: 1.72;
        margin-top: 1rem;
        padding: 1.35rem;
        white-space: pre-wrap;
    }}

    .report-box strong {{
        font-family: var(--report-font);
        font-size: 1.25rem;
        font-weight: 700;
    }}

    .source-grid {{
        display: grid;
        gap: 0.8rem;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        margin-top: 1rem;
    }}

    .source-card {{
        background: var(--surface-2);
        border: 2px solid var(--border);
        box-shadow: 4px 4px 0 var(--shadow);
        color: var(--text);
        padding: 0.95rem;
    }}

    .source-card h4 {{
        color: var(--text);
        font-size: 0.95rem;
        font-weight: 850;
        letter-spacing: -0.02em;
        line-height: 1.25;
        margin: 0 0 0.45rem;
    }}

    .source-card p {{
        color: var(--muted);
        font-size: 0.82rem;
        font-weight: 700;
        line-height: 1.35;
        margin: 0;
        overflow-wrap: anywhere;
    }}

    .caption {{
        color: var(--muted);
        font-size: 0.82rem;
        font-weight: 800;
        margin-top: 0.2rem;
    }}

    div[data-testid="stAlert"] {{
        border: 2px solid var(--border);
        border-radius: 0;
    }}

    div[data-testid="stForm"] {{
        background: var(--surface);
        border: 2px solid var(--border);
        border-radius: 0 !important;
        box-shadow: 6px 6px 0 var(--shadow);
        color: var(--text);
        margin: 1.2rem 0 1.4rem;
        min-height: 540px;
        padding: clamp(2rem, 5vw, 4rem) 2rem 2.2rem;
    }}

    div[data-testid="stForm"] form {{
        border-radius: 0 !important;
        min-height: 440px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }}

    div[data-testid="stForm"] .hero {{
        margin-bottom: 2.2rem;
    }}

    @media (max-width: 760px) {{
        .topbar, .nav {{
            align-items: flex-start;
            flex-direction: column;
            gap: 0.75rem;
        }}

        .content {{
            padding: 1.4rem;
        }}

        .meta-grid,
        .source-grid {{
            grid-template-columns: 1fr;
        }}
    }}
</style>
""",
    unsafe_allow_html=True,
)


st.markdown(f'<div class="{theme_class}">', unsafe_allow_html=True)
st.markdown(
    f"""
<header class="app-shell topbar">
        <div class="brand">
            <div class="logo">{html.escape(logo_text)}</div>
            <div class="brand-name">Research<br>Assistant</div>
        </div>
        <nav class="nav">
            <span class="active">Research</span>
            <span>Sources</span>
            <span>Reports</span>
            <span>About</span>
        </nav>
        <div class="mode-pill">{'Dark' if dark_mode else 'Light'} mode</div>
</header>
<section class="content">
""",
    unsafe_allow_html=True,
)


with st.form("research_search", clear_on_submit=False):
    st.markdown(
        """
        <div class="hero">
            <h1>Find sharper answers.</h1>
            <p>Ask one research question. The agent team searches, summarizes, and writes a clean report.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left_pad, search_col, right_pad = st.columns([1, 6, 1], gap="small")
    with search_col:
        topic = st.text_input(
            "Research topic",
            placeholder="Example: self-healing RAG systems for enterprise knowledge bases",
            label_visibility="collapsed",
        )

    button_left, button_col, button_right = st.columns([3, 2, 3], gap="small")
    with button_col:
        run_btn = st.form_submit_button("Run search", type="primary", use_container_width=True)

st.markdown(
    f"""
<div class="meta-grid">
    <aside class="panel">
        <h3>Settings</h3>
        <div class="filters">
            <div class="filter-line"><span class="box on"></span> Sources <span class="setting-value">{source_count}</span></div>
            <div class="filter-line"><span class="box on"></span> Length <span class="setting-value">{html.escape(report_length)}</span></div>
            <div class="filter-line"><span class="box on"></span> Tone <span class="setting-value">{html.escape(tone)}</span></div>
            <div class="filter-line"><span class="box {'on' if include_citations else ''}"></span> Citations <span class="setting-value">{'On' if include_citations else 'Off'}</span></div>
        </div>
    </aside>
    <section class="panel">
        <div class="pipeline-title">
            <h2>Agent pipeline</h2>
            <span>3 steps</span>
        </div>
""",
    unsafe_allow_html=True,
)

a1 = st.empty()
a2 = st.empty()
a3 = st.empty()


def card(placeholder, step_name, desc, status="idle"):
    cls = {"idle": "", "active": "active", "done": "done"}[status]
    placeholder.markdown(
        f"""
<div class="agent-card {cls}">
    <div class="agent-label">{html.escape(step_name)}</div>
    <div class="agent-name">{html.escape(desc)}</div>
</div>
""",
        unsafe_allow_html=True,
    )


card(a1, "Step 01 / Searcher", "Waiting for a topic", "idle")
card(a2, "Step 02 / Summarizer", "Waiting for sources", "idle")
card(a3, "Step 03 / Writer", "Waiting for summaries", "idle")

st.markdown("</section></div>", unsafe_allow_html=True)


if run_btn:
    if not groq_key or not tavily_key:
        st.error("Enter both API keys in the sidebar.")
    elif not topic.strip():
        st.warning("Enter a research topic.")
    else:
        os.environ["GROQ_API_KEY"] = groq_key
        os.environ["TAVILY_API_KEY"] = tavily_key

        try:
            card(a1, "Step 01 / Searcher", f"Searching for: {topic}", "active")
            card(a2, "Step 02 / Summarizer", "Waiting for search results", "idle")
            card(a3, "Step 03 / Writer", "Waiting to write report", "idle")

            with st.spinner("Running research pipeline..."):
                start = time.time()
                result = run_research(
                    topic=topic.strip(),
                    source_count=source_count,
                    report_length=report_length,
                    tone=tone,
                    include_citations=include_citations,
                )
                elapsed = round(time.time() - start, 1)

            card(a1, "Step 01 / Searcher", f"Found {len(result['search_results'])} sources", "done")
            card(a2, "Step 02 / Summarizer", f"Summarized {len(result['summaries'])} results", "done")
            card(a3, "Step 03 / Writer", "Report ready", "done")

            source_cards = []
            for index, source in enumerate(result["search_results"], start=1):
                title = html.escape(source.get("title") or f"Source {index}")
                url = html.escape(source.get("url") or "No URL returned")
                source_cards.append(
                    f"""
<article class="source-card">
    <h4>{index}. {title}</h4>
    <p>{url}</p>
</article>
"""
                )

            st.markdown(
                f"""
<section class="panel" style="margin-top: 1rem;">
    <div class="pipeline-title">
        <h2>Sources</h2>
        <span>{len(result["search_results"])} found</span>
    </div>
    <div class="source-grid">
        {''.join(source_cards)}
    </div>
</section>
""",
                unsafe_allow_html=True,
            )

            safe_report = html.escape(result["final_report"])
            st.markdown(
                f"""
<section class="report-box">
    <strong>Research report</strong>
    <div class="caption">{html.escape(topic.strip())} / {elapsed}s</div>
    <br>
    {safe_report}
</section>
""",
                unsafe_allow_html=True,
            )

            st.download_button(
                label="Download report",
                data=result["final_report"],
                file_name=f"research_{topic[:30].replace(' ', '_')}.txt",
                mime="text/plain",
            )

        except Exception as e:
            st.error(f"Something went wrong: {e}")


st.markdown("</section></div>", unsafe_allow_html=True)

import streamlit as st


def inject_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            color: #1A1A2E;
        }
        .stApp { background-color: #F5F6F8; }

        /* ── Header ── */
        .otcx-header {
            background: #FFFFFF;
            border-bottom: 3px solid #B22222;
            padding: 0.9rem 2rem;
            margin: -1rem -1rem 1.5rem -1rem;
            display: flex;
            align-items: center;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        }
        .otcx-logo {
            font-size: 1.8rem;
            font-weight: 700;
            color: #1A1A2E;
            letter-spacing: -0.04em;
            line-height: 1;
        }
        .otcx-logo span { color: #B22222 !important; }
        .otcx-tagline {
            font-size: 0.65rem;
            color: #1A1A2E;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            margin-top: 0.15rem;
        }

        /* ── Section Headers ── */
        .sec-hdr {
            font-size: 0.68rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.14em;
            color: #1A1A2E;
            border-bottom: 2px solid #B22222;
            padding-bottom: 0.45rem;
            margin-bottom: 0.8rem;
        }

        /* ── Metric Cards ── */
        .kpi-card {
            background: #FFFFFF;
            border: 1px solid #CED4DA;
            border-top: 3px solid #B22222;
            padding: 1.1rem 1.3rem;
            height: 100%;
            box-shadow: 0 1px 2px rgba(0,0,0,0.03);
        }
        .kpi-label {
            font-size: 0.65rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            color: #1A1A2E;
            margin-bottom: 0.35rem;
        }
        .kpi-value {
            font-size: 1.65rem;
            font-weight: 700;
            color: #1A1A2E;
            line-height: 1;
            margin-bottom: 0.2rem;
            font-family: 'IBM Plex Mono', monospace;
        }
        .kpi-sub { font-size: 0.72rem; color: #1A1A2E; }
        .c-pos { color: #28A745; font-weight: 600; }
        .c-neg { color: #DC3545; font-weight: 600; }

        /* ── Market Table ── */
        .mkt-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.82rem;
        }
        .mkt-table th {
            font-size: 0.62rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.09em;
            color: #1A1A2E;
            border-bottom: 2px solid #CED4DA;
            padding: 0.55rem 0.7rem;
            text-align: right;
            white-space: nowrap;
            background: #F8F9FA;
        }
        .mkt-table th.left { text-align: left; }
        .mkt-table td {
            padding: 0.55rem 0.7rem;
            border-bottom: 1px solid #E9ECEF;
            text-align: right;
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.8rem;
            white-space: nowrap;
            color: #1A1A2E;
        }
        .mkt-table td.left {
            text-align: left;
            font-family: 'Inter', sans-serif;
        }
        .mkt-table td.isin {
            color: #B22222;
            font-weight: 500;
            font-family: 'IBM Plex Mono', monospace;
        }
        .mkt-table td.isin a {
            color: #B22222;
            text-decoration: none;
        }
        .mkt-table td.isin a:hover {
            text-decoration: underline;
            color: #8B1A1A;
        }
        .mkt-table td.name {
            font-family: 'Inter', sans-serif;
            font-weight: 500;
            max-width: 180px;
            overflow: hidden;
            text-overflow: ellipsis;
            color: #1A1A2E;
        }
        .mkt-table td.sektor {
            font-size: 0.75rem;
            color: #1A1A2E;
        }
        .mkt-table td.flag {
            text-align: center;
            font-size: 0.9rem;
        }
        .mkt-table tr:hover { background: #F0F1F3; }
        .pos { color: #28A745 !important; }
        .neg { color: #DC3545 !important; }

        /* ── Badges ── */
        .bdg {
            display: inline-block;
            padding: 0.15rem 0.5rem;
            font-size: 0.6rem;
            font-weight: 700;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            border-radius: 2px;
        }
        .bdg-clean    { background: #D4EDDA; color: #155724; }
        .bdg-watch    { background: #FFF3CD; color: #664D03; }
        .bdg-alert    { background: #FFE0CC; color: #6A3200; }
        .bdg-critical { background: #F8D7DA; color: #58151C; }
        .bdg-severe   { background: #E8C4D0; color: #4A0E1E; }
        .bdg-extreme  { background: #D4A0B0; color: #3A0010; }

        /* ── Risk Card (clickable) ── */
        .risk-card {
            background: #FFFFFF;
            border: 1px solid #CED4DA;
            border-top: 3px solid #CED4DA;
            padding: 1rem 1.2rem;
            cursor: pointer;
            transition: all 0.15s ease;
            box-shadow: 0 1px 2px rgba(0,0,0,0.03);
        }
        .risk-card:hover { transform: translateY(-1px); box-shadow: 0 3px 8px rgba(0,0,0,0.08); }
        .risk-card.active { border-color: #B22222; border-top-width: 3px; }

        /* ── Tabs ── */
        .stTabs [data-baseweb="tab-list"] {
            gap: 0;
            background: #FFFFFF;
            border-bottom: 2px solid #CED4DA;
        }
        .stTabs [data-baseweb="tab"] {
            padding: 0.7rem 1.4rem;
            font-size: 0.82rem;
            font-weight: 500;
            letter-spacing: 0.02em;
            color: #1A1A2E;
            border-radius: 0;
            background: transparent;
            border-bottom: 2px solid transparent;
            margin-bottom: -2px;
        }
        .stTabs [aria-selected="true"] {
            color: #B22222 !important;
            border-bottom: 2px solid #B22222 !important;
            background: transparent !important;
        }

        /* ── Sidebar ── */
        section[data-testid="stSidebar"] { background: #FFFFFF; border-right: 1px solid #CED4DA; }

        /* ── Live dot ── */
        .live-dot {
            display: inline-flex; align-items: center; gap: 0.4rem;
            font-size: 0.68rem; font-weight: 700; text-transform: uppercase;
            letter-spacing: 0.1em; color: #28A745;
        }
        .dot {
            width: 6px; height: 6px; border-radius: 50%;
            background: #28A745; animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.35; }
        }

        /* ── Math formula ── */
        .math-note {
            font-size: 0.72rem;
            color: #1A1A2E;
            font-style: italic;
            font-family: 'IBM Plex Mono', monospace;
            margin-bottom: 0.5rem;
        }

        /* ── Streamlit override: selectbox, text_input, number_input labels ── */
        .stSelectbox label, .stTextInput label, .stNumberInput label,
        .stMultiSelect label, .stSlider label, .stCheckbox label,
        .stRadio label {
            color: #1A1A2E !important;
        }
        .stSelectbox [data-baseweb="select"] span,
        .stMultiSelect [data-baseweb="select"] span {
            color: #1A1A2E !important;
        }
        div[data-testid="stMetricLabel"] p {
            color: #1A1A2E !important;
        }
        div[data-testid="stMetricValue"] div {
            color: #1A1A2E !important;
        }
        /* Checkbox label text — override Streamlit grey */
        .stCheckbox label p, .stCheckbox label span,
        .stCheckbox [data-testid="stMarkdownContainer"] p {
            color: #1A1A2E !important;
        }
        /* Selectbox / multiselect chosen value text */
        [data-baseweb="select"] .css-1dimb5e-singleValue,
        [data-baseweb="select"] [data-testid="stMarkdownContainer"],
        [data-baseweb="tag"] span {
            color: #1A1A2E !important;
        }

        /* ── Comprehensive Streamlit text contrast overrides ── */
        /* Placeholder text in all input/select widgets */
        [data-baseweb="select"] [data-testid="stMarkdownContainer"] p,
        [data-baseweb="select"] .css-1wa3eu0-placeholder,
        [data-baseweb="select"] div[class*="placeholder"],
        [data-baseweb="select"] div[aria-selected] span,
        [data-baseweb="input"] input::placeholder,
        .stTextInput input::placeholder,
        .stTextInput input,
        .stNumberInput input {
            color: #1A1A2E !important;
            opacity: 1 !important;
            -webkit-text-fill-color: #1A1A2E !important;
        }
        /* Search / text input background → beige */
        .stTextInput input {
            background-color: rgb(235, 226, 205) !important;
        }
        /* All text inside selectbox/multiselect controls */
        [data-baseweb="select"] div,
        [data-baseweb="select"] span,
        [data-baseweb="select"] p,
        .stSelectbox div[data-baseweb="select"] > div > div,
        .stMultiSelect div[data-baseweb="select"] > div > div {
            color: #1A1A2E !important;
        }
        /* Dropdown menu items */
        [data-baseweb="menu"] li,
        [data-baseweb="menu"] li span,
        [role="listbox"] li,
        [role="option"] span,
        [role="option"] {
            color: #1A1A2E !important;
        }
        /* Dropdown popup / menu background → beige (ultra-broad to defeat dark theme) */
        [data-baseweb="popover"],
        [data-baseweb="popover"] > div,
        [data-baseweb="popover"] div,
        [data-baseweb="popover"] ul,
        [data-baseweb="popover"] li,
        [data-baseweb="menu"],
        [data-baseweb="menu"] ul,
        [data-baseweb="menu"] div,
        [role="listbox"],
        [role="listbox"] ul,
        [role="listbox"] div,
        [role="listbox"] li,
        [role="option"],
        [data-baseweb="select"] [data-baseweb="popover"] div,
        div[data-baseweb="popover"] > div > ul {
            background-color: rgb(235, 226, 205) !important;
        }
        /* Dropdown list items hover state → slightly darker beige */
        [data-baseweb="menu"] li:hover,
        [role="listbox"] li:hover,
        [role="option"]:hover,
        [role="option"][aria-selected="true"] {
            background-color: rgb(220, 210, 185) !important;
        }
        /* Dropdown arrow → black (was invisible white on beige) */
        [data-baseweb="select"] svg {
            color: #1A1A2E !important;
            fill: #1A1A2E !important;
        }
        /* Toggle / checkbox description text */
        .stCheckbox > label > div[data-testid="stMarkdownContainer"] {
            color: #1A1A2E !important;
        }
        /* General text elements that Streamlit may render in grey */
        .stMarkdown p, .stMarkdown span, .stMarkdown li,
        .stMarkdown div, .stText, .stCaption {
            color: #1A1A2E !important;
        }
        /* ── Tier-specific KPI value colours (must appear after .stMarkdown rule) ── */
        .stMarkdown .kpi-value.kpi-tier-clean  { color: #1B6B2E !important; }
        .stMarkdown .kpi-value.kpi-tier-alert   { color: #7D3C00 !important; }
        .stMarkdown .kpi-value.kpi-tier-critical { color: #721C24 !important; }
        .stMarkdown .kpi-value.kpi-tier-severe  { color: #7D1128 !important; }
        .stMarkdown .kpi-value.kpi-tier-extreme { color: #4A0010 !important; }
        /* ── Logo span override (must appear after .stMarkdown rule) ── */
        .stMarkdown .otcx-logo span { color: #B22222 !important; }
        /* Streamlit expander header text */
        .streamlit-expanderHeader p, .streamlit-expanderHeader span {
            color: #1A1A2E !important;
        }
        /* Tooltip and help text */
        .stTooltipIcon svg { color: #1A1A2E !important; }
        div[data-testid="stTooltipContent"] p { color: #1A1A2E !important; }

        /* ── Neutral Streamlit buttons — warm sand instead of bright red ── */
        .stButton > button {
            background-color: rgb(235, 226, 205) !important;
            color: #1A1A2E !important;
            border: 1px solid #C8BFA5 !important;
            font-weight: 600 !important;
            transition: background-color 0.2s ease, border-color 0.2s ease,
                        color 0.2s ease !important;
        }
        .stButton > button:hover {
            background-color: rgb(231, 221, 199) !important;
            border-color: #B9AE8D !important;
            box-shadow: none !important;
        }
        .stButton > button:focus {
            box-shadow: 0 0 0 2px rgba(185,174,141,0.35) !important;
        }
        /* Download button — neutral style aligned with control buttons */
        .stDownloadButton > button {
            background-color: rgb(235, 226, 205) !important;
            color: #1A1A2E !important;
            border: 1px solid #C8BFA5 !important;
            font-weight: 600 !important;
            transition: background-color 0.2s ease, border-color 0.2s ease,
                        color 0.2s ease !important;
        }
        .stDownloadButton > button:hover {
            background-color: rgb(231, 221, 199) !important;
            border-color: #B9AE8D !important;
            box-shadow: none !important;
        }

        /* Neutral multiselect / dropdown controls */
        .stMultiSelect [data-baseweb="select"] > div,
        .stSelectbox [data-baseweb="select"] > div {
            background-color: rgb(247, 243, 234) !important;
            border-color: #D8CFB7 !important;
        }
        .stMultiSelect [data-baseweb="tag"] {
            background-color: rgb(235, 226, 205) !important;
            border: 1px solid #C8BFA5 !important;
        }
        .stMultiSelect [data-baseweb="tag"] span {
            color: #1A1A2E !important;
        }

        /* ── Misc ── */
        #MainMenu, footer, header { visibility: hidden; }
        .block-container { padding-top: 1rem; padding-bottom: 2rem; }
        p, span, li, div { color: inherit; }

        /* ── Anomaly detail table ── */
        .anomaly-detail-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.8rem;
        }
        .anomaly-detail-table th {
            font-size: 0.62rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.09em;
            color: #1A1A2E;
            border-bottom: 2px solid #CED4DA;
            padding: 0.5rem 0.6rem;
            text-align: right;
            background: #F8F9FA;
        }
        .anomaly-detail-table th.left { text-align: left; }
        .anomaly-detail-table td {
            padding: 0.5rem 0.6rem;
            border-bottom: 1px solid #E9ECEF;
            text-align: right;
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.78rem;
            color: #1A1A2E;
        }
        .anomaly-detail-table td.left { text-align: left; font-family: 'Inter', sans-serif; }
        .anomaly-detail-table tr:hover { background: #F0F1F3; }


        </style>
        """,
        unsafe_allow_html=True,
    )

"""Design system for the Smart Road research dashboard.

Streamlit widgets remain native and keyboard accessible; CSS is presentation only.
"""
from __future__ import annotations

import streamlit as st

CSS = r"""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=IBM+Plex+Sans+Arabic:wght@400;500;600;700&display=swap');
:root { --sr-accent: #2879f2; --sr-ink: #161e2d; --sr-subtle: #7c8795; --sr-line: #e7ebf1; }
html, body, [class*="css"], [data-testid="stAppViewContainer"] {
  font-family: 'DM Sans','IBM Plex Sans Arabic',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
}
.stApp { background: #f7f9fc; color: var(--sr-ink); }
[data-testid="stHeader"] { background: rgba(247,249,252,.9); backdrop-filter: blur(14px); }
[data-testid="stToolbar"], [data-testid="stDecoration"] {visibility:hidden;}
.block-container { max-width: 1390px; padding-top: 1.7rem; padding-bottom: 5rem; }
h1,h2,h3 { letter-spacing: -.035em; color:#182337; }
h1 {font-weight:750;}
h2 {font-weight:700; }
[data-testid="stVerticalBlock"] > div {min-width:0;}
.sr-topbar { display:flex; align-items:center; justify-content:space-between; gap:14px;
             margin:0 0 26px; padding-bottom:17px; border-bottom:1px solid #e6eaf1; }
.sr-brand { display:flex; align-items:center; gap:12px; }
.sr-symbol { display:grid;place-items:center;width:43px;height:43px;border-radius:14px;
             background:#152a47;color:white;box-shadow:0 7px 19px #152a4717; }
.sr-wordmark {font-size:19px;font-weight:800;letter-spacing:-.05em;line-height:1.18;}
.sr-wordmark small {display:block;color:#8590a0;font-size:11px;letter-spacing:.09em;font-weight:700;margin-top:4px;}
.sr-topright {display:flex;align-items:center;gap:10px;color:#7b8696;font-size:11px;font-weight:700;letter-spacing:.07em;}
.sr-dot {display:inline-block;width:7px;height:7px;border-radius:50%;background:#3caf79;margin-right:6px;}
.sr-topchip {border:1px solid #e6eaf0;border-radius:99px;padding:8px 12px;background:white;}
.sr-hero { display:grid;grid-template-columns: 1fr auto;gap:32px;align-items:center;
           border:1px solid #e7ecf4;border-radius:24px;padding:32px 38px;margin-bottom:23px;
           background:linear-gradient(118deg,#ffffff 0%,#fff 67%,#f0f6ff 100%);
           box-shadow:0 12px 34px rgba(27,51,93,.035); }
.sr-eyebrow {font-size:11px;letter-spacing:.16em;font-weight:800;text-transform:uppercase;color:#3b83e6;margin:0 0 12px;}
.sr-hero h1 {font-size:clamp(29px,3.1vw,46px);line-height:1.14;letter-spacing:-.055em;margin:0 0 14px;
             font-weight:800;color:#17243a;}
.sr-hero p {font-size:14px;line-height:1.8;max-width:660px;color:#677485;margin:0;}
.sr-hero-mini {display:flex;flex-direction:column;gap:12px;min-width:175px;}
.sr-mini-stat {background:white;border:1px solid #e7edf5;border-radius:16px;padding:14px 16px;}
.sr-mini-stat b {font-size:20px;color:#172438;display:block;line-height:1.25;}
.sr-mini-stat span {font-size:10px;color:#8090a0;letter-spacing:.08em;font-weight:700;}
.sr-section-label {display:flex;align-items:center;justify-content:space-between;margin:26px 0 15px;gap:12px;}
.sr-section-label h3 {font-size:17px;font-weight:750;letter-spacing:-.035em;margin:0;}
.sr-section-label p {color:#8b95a2;font-size:12px;margin:0;}
.sr-metric-grid {display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:9px 0 22px;}
.sr-metric {background:white;border:1px solid #e6ebf2;border-radius:18px;padding:19px 20px;
            min-height:117px;box-shadow:0 5px 20px rgba(30,52,85,.025);}
.sr-metric .sr-metric-kicker {font-size:11px;font-weight:650;color:#8a94a2;margin-bottom:14px;display:block;}
.sr-metric strong {font-size:29px;letter-spacing:-.055em;font-weight:760;color:#1a2b43;line-height:1;}
.sr-metric .sr-metric-unit {font-size:11px;font-weight:600;color:#9ba6b5;margin-left:7px;}
.sr-metric.positive strong {color:#237a5c;}
.sr-metric.warn strong {color:#bf7926;}
.sr-tag {display:inline-flex;align-items:center;border:1px solid #dfe7f0;border-radius:99px;
         background:#f6f9fc;color:#66778a;font-size:11px;font-weight:700;padding:5px 10px;white-space:nowrap;}
.sr-tag.blue {background:#eff6ff;border-color:#dbeaff;color:#2970c8;}
.sr-tag.green {background:#eaf8f1;border-color:#d1efde;color:#21865b;}
.sr-tag.amber {background:#fff7e8;border-color:#ffe8bd;color:#9f6c22;}
.sr-tag.red {background:#fff0ef;border-color:#f9d8d4;color:#b44942;}
.sr-empty {display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:340px;
           border:1px dashed #d6e0ec;border-radius:20px;background:#fafcff;text-align:center;padding:24px;}
.sr-empty-icon {height:64px;width:64px;border-radius:20px;background:#eaf2ff;
                display:grid;place-items:center;color:#417ace;margin-bottom:18px;font-size:29px;}
.sr-empty strong {font-size:17px;color:#20334e;}
.sr-empty p {font-size:12px;color:#8492a3;max-width:340px;margin:12px 0 0;line-height:1.8;}
.sr-footnote {font-size:11px;color:#8b96a4;line-height:1.85;margin:6px 0 14px;}
.sr-event {display:flex;align-items:flex-start;gap:13px;padding:16px;
           background:white;border:1px solid #e7ebf1;border-radius:16px;margin:9px 0;}
.sr-event-icon {border-radius:12px;padding:8px;background:#f1f5ff;color:#2f70bf;font-size:16px;}
.sr-event strong {display:block;color:#26354c;font-size:13px;margin-bottom:5px;}
.sr-event p {color:#7b8998;font-size:11px;line-height:1.6;margin:0;}
.sr-event time {margin-left:auto;color:#8e9aa8;white-space:nowrap;font-size:11px;font-variant-numeric:tabular-nums;}
.sr-tech-grid {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:11px;margin:16px 0;}
.sr-tech {background:white;border:1px solid #e6ebf1;border-radius:17px;padding:18px;}
.sr-tech b {display:block;font-size:13px;color:#243650;margin:12px 0 7px;}
.sr-tech p {color:#8a95a4;font-size:11px;margin:0;line-height:1.7;}
/* Native Streamlit controls: retain keyboard focus and semantics */
.stButton > button[kind="primary"] {background:#2675df;border:1px solid #2675df;border-radius:11px;
  color:white;box-shadow:0 6px 16px #2675df27;min-height:44px;font-weight:700;}
.stButton > button[kind="primary"]:hover {background:#1d62c5;color:white;border-color:#1d62c5;}
.stButton > button, .stDownloadButton > button {border-radius:11px;min-height:41px;font-weight:650;}
div[data-testid="stFileUploader"] {border-radius:16px;overflow:hidden;}
[data-testid="stExpander"] {background:white;border:1px solid #e7ebf1 !important;border-radius:16px !important;}
[data-testid="stVerticalBlockBorderWrapper"] > div {border:1px solid #e6eaf1 !important;
  border-radius:19px !important;background:white;box-shadow:0 7px 24px #182f4a05;}
div[data-testid="stRadio"] > div {gap:12px;}
div[data-testid="stAlert"] {border-radius:13px;border:1px solid #e4eaf3;}
[data-testid="stDataFrame"] {border-radius:14px;overflow:hidden;}
@media(max-width:900px) {
 .block-container {padding:1.0rem .9rem 4rem;}
 .sr-hero {grid-template-columns:1fr;padding:24px 22px;gap:18px;border-radius:20px;}
 .sr-hero-mini {flex-direction:row;min-width:0;}
 .sr-mini-stat{flex:1;}
 .sr-metric-grid {grid-template-columns:repeat(2,minmax(0,1fr));}
 .sr-topright {display:none;}
 .sr-tech-grid {grid-template-columns:1fr;}
}
@media(max-width:480px) {
 .sr-hero-mini {display:none;}
 .sr-metric{min-height:104px;padding:16px;}
 .sr-metric strong {font-size:25px;}
 .sr-section-label{align-items:flex-start;flex-direction:column;}
 .sr-brand .sr-wordmark{font-size:17px;}
}

.sr-results-header {padding:27px 32px 23px;margin:30px 0 12px;border:1px solid #e3ebf7;
background:linear-gradient(125deg,#fff,#f3f8ff);border-radius:22px;}
.sr-results-header h2 {font-size:clamp(25px,3vw,37px);margin:0 0 9px;letter-spacing:-.055em;}
.sr-results-header p {font-size:13px;color:#7b8a9f;margin:0;}
.sr-metric-grid.sr-metric-six{grid-template-columns:repeat(3,minmax(0,1fr))}
@media(max-width:700px){.sr-metric-grid.sr-metric-six{grid-template-columns:repeat(2,minmax(0,1fr))}
.sr-results-header{padding:22px 19px}}
</style>
"""


def apply_theme():
    st.markdown(CSS, unsafe_allow_html=True)

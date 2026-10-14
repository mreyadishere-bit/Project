"""Small accessible presentation layer for the hosted Smart Road dashboard.

View functions accept only recorded measurements/review suggestions.
Dynamic text is HTML-escaped before rendering in reusable cards.
"""
from __future__ import annotations

from html import escape

import streamlit as st


STYLE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&display=swap');
:root {
  --road-ink:#12213b; --road-muted:#68788e; --road-line:#e6ecf3;
  --road-blue:#315fd9; --road-surface:#ffffff; --road-bg:#f5f7fb;
}
html,body,[data-testid="stAppViewContainer"],[data-testid="stApp"] {
  font-family:'DM Sans',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  color:var(--road-ink);
}
[data-testid="stAppViewContainer"]{
 background:radial-gradient(ellipse 850px 420px at 12% 0%,#eaf2ff 0%,transparent 70%),#f5f7fb;
}
[data-testid="stHeader"]{background:rgba(245,247,251,.82);backdrop-filter:blur(14px)}
[data-testid="stDecoration"]{display:none}
.block-container{max-width:1260px;padding-top:1.5rem;padding-bottom:5rem}
h1,h2,h3{color:#11223e!important;letter-spacing:-.046em;font-weight:750!important}
h1{font-size:clamp(2rem,4vw,3.25rem)!important;line-height:1.14!important}
h2{font-size:clamp(1.3rem,2.4vw,1.8rem)!important}
p{line-height:1.65}
[data-testid="stVerticalBlock"] > div{min-width:0}
div[data-testid="stVerticalBlockBorderWrapper"]{
 border:1px solid var(--road-line)!important;
 border-radius:19px!important;background:rgba(255,255,255,.94)!important;
 box-shadow:0 5px 24px rgba(29,52,89,.038);
}
[data-testid="stVerticalBlockBorderWrapper"] > div{border-color:transparent!important}
div[data-testid="stMetric"]{
 padding:16px 18px;background:white;border:1px solid var(--road-line);
 border-radius:16px;box-shadow:0 3px 15px rgba(20,43,77,.03);
}
[data-testid="stMetricLabel"]{font-weight:600;color:#65758c}
[data-testid="stMetricValue"]{color:#12213b;font-weight:750}
div[data-testid="stAlert"]{border-radius:14px}
[data-testid="stFileUploader"]{border-radius:17px;overflow:hidden}
[data-testid="stFileUploaderDropzone"]{border:1px dashed #b5c6e2;background:#f7faff;border-radius:15px}
[data-testid="stFileUploaderDropzone"]:hover{background:#eff5ff;border-color:#4776e0}
.stButton button[kind="primary"],[data-testid="stBaseButton-primary"]{
 background:#315fd9!important;border:1px solid #315fd9!important;
 border-radius:12px!important;min-height:46px;font-weight:650;
 box-shadow:0 5px 12px rgba(49,95,217,.13);
}
.stButton button{border-radius:12px!important;font-weight:600}
.stButton button:hover{transform:translateY(-1px);transition:transform .14s ease}
[data-testid="stDownloadButton"] button{border-radius:12px}
[data-testid="stTabs"] [data-baseweb="tab-list"]{
 gap:6px;flex-wrap:wrap;border-bottom:1px solid var(--road-line);
 padding-bottom:7px;
}
[data-testid="stTabs"] button[role="tab"]{
 padding:9px 15px;border-radius:11px;color:#556984;font-weight:650;
}
[data-testid="stTabs"] button[aria-selected="true"]{
 background:#eaf1ff;color:#244db1!important;
}
[data-testid="stExpander"]{border-radius:15px!important;overflow:hidden;background:white}
[data-testid="stExpander"] summary{font-weight:650}
[data-testid="stDataFrame"],video,iframe{border-radius:14px;overflow:hidden}
.road-brand{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:0 0 27px}
.road-brand-left{display:flex;align-items:center;gap:12px}
.road-logo{width:39px;height:39px;display:grid;place-items:center;
 background:#152b53;color:white;border-radius:12px;font-size:19px}
.road-brand-name{color:#142846;font-size:17px;font-weight:800;letter-spacing:-.04em}
.road-brand-meta{font-size:11px;font-weight:700;letter-spacing:.12em;color:#7387a1;text-transform:uppercase}
.road-state{font-size:11px;color:#3669b7;border:1px solid #dce8f7;border-radius:99px;
 padding:8px 12px;background:white;white-space:nowrap;font-weight:700}
.road-hero{border-radius:25px;background:linear-gradient(115deg,#14284b,#1c3b6b 64%,#295eb6);
 padding:clamp(24px,4vw,41px);color:#fff;margin:6px 0 23px;
 box-shadow:0 16px 36px rgba(17,43,89,.14);position:relative;overflow:hidden}
.road-hero:after{content:"";pointer-events:none;position:absolute;right:-65px;top:-140px;
 width:360px;height:360px;border-radius:50%;border:70px solid rgba(255,255,255,.045)}
.road-kicker{color:#a8c9ff;text-transform:uppercase;letter-spacing:.14em;font-size:11px;font-weight:750}
.road-hero h1,.road-hero h2{color:white!important;margin:12px 0!important;
 font-size:clamp(24px,3.8vw,42px)!important;max-width:780px;font-weight:750!important}
.road-hero p{color:#d7e5fa;font-size:14px;line-height:1.7;max-width:780px;margin:0}
.road-hero .road-hero-foot{margin-top:18px;font-size:12px;color:#b8cdec}
.road-section{display:flex;justify-content:space-between;align-items:flex-end;
 gap:16px;margin:29px 0 14px}
.road-section h3{margin:0;font-size:clamp(19px,2.1vw,25px);letter-spacing:-.04em}
.road-section p{color:#6c7d92;margin:6px 0 0;font-size:13px}
.road-eyebrow{font-size:10px;text-transform:uppercase;letter-spacing:.17em;
 color:#5074bb;font-weight:800;margin-bottom:5px}
.road-metric-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:13px;margin:14px 0 22px}
.road-metric{background:white;border:1px solid var(--road-line);border-radius:17px;
 padding:20px 20px 17px;min-width:0;box-shadow:0 6px 24px rgba(19,40,76,.035)}
.road-metric .k{font-size:11px;font-weight:700;letter-spacing:.01em;color:#697c93}
.road-metric .v{font-size:clamp(23px,3vw,32px);font-weight:800;color:#142846;
 letter-spacing:-.045em;margin:9px 0 5px;line-height:1.15;word-break:break-word}
.road-metric .h{font-size:11px;color:#8492a5;line-height:1.5}
.road-issue-card,.road-reco-card{background:#fff;border:1px solid #e5ecf5;
 border-radius:17px;padding:18px 19px;margin:0 0 10px;min-height:150px;
 box-shadow:0 4px 14px rgba(22,45,77,.03)}
.road-issue-card{border-left:4px solid #e4a429}
.road-issue-card[data-level="critical"]{border-left-color:#d74850}
.road-issue-card[data-level="risk"]{border-left-color:#ed8740}
.road-issue-card[data-level="safe"]{border-left-color:#319b77}
.road-card-top{display:flex;gap:11px;justify-content:space-between;align-items:center;margin-bottom:10px}
.road-card-title{font-size:16px;font-weight:750;color:#152641;letter-spacing:-.03em;line-height:1.4}
.road-pill{display:inline-flex;align-items:center;padding:5px 9px;white-space:nowrap;
 font-size:10px;letter-spacing:.02em;font-weight:800;border-radius:20px;background:#fff3de;color:#946015}
.road-pill[data-level="critical"]{background:#fff0f0;color:#b62d37}
.road-pill[data-level="risk"]{background:#fff1e6;color:#ad5017}
.road-pill[data-level="safe"]{background:#eaf8f1;color:#187b56}
.road-pill[data-level="unknown"]{background:#edf1f7;color:#53647d}
.road-card-copy{font-size:12.5px;line-height:1.7;color:#5b6e83;margin:6px 0 12px}
.road-card-meta{font-size:11px;color:#76869b;line-height:1.65;margin-top:6px}
.road-card-action{padding:11px 13px;border-radius:10px;background:#f1f6ff;
 color:#255099;font-size:12px;line-height:1.6;margin-top:10px}
.road-legend{display:flex;flex-wrap:wrap;gap:7px;margin:8px 0 16px}
.road-legend span{border-radius:99px;font-size:11px;padding:7px 11px;font-weight:700;
 border:1px solid var(--road-line);background:#fff;color:#5b6f88}
.road-legend i{display:inline-block;width:8px;height:8px;border-radius:100%;margin-right:6px}
.road-notice{border:1px solid #dde8f9;background:#f3f7ff;border-radius:13px;
 padding:12px 15px;color:#42618c;font-size:12px;line-height:1.75;margin:10px 0 17px}
.road-timeline{font-variant-numeric:tabular-nums;font-size:12px;font-weight:750;color:#4467aa}
@media(max-width:900px){.road-metric-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:700px){
 .block-container{padding:1rem .9rem 3.6rem}
 .road-hero{padding:24px 21px;border-radius:21px}
 .road-brand{margin-bottom:20px}
 .road-section{margin-top:22px}
 .road-metric{padding:16px}
 .road-issue-card,.road-reco-card{min-height:0}
 [data-testid="stTabs"] [data-baseweb="tab-list"]{flex-wrap:nowrap;overflow-x:auto}
}
@media(max-width:430px){.road-metric-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
 .road-metric{padding:13px}.road-metric .v{font-size:23px}
 .road-state{display:none}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;transition:none!important}}
</style>
"""


def _safe(value):
    return escape(str(value), quote=True)


def brand():
    st.markdown(
        '<div class="road-brand"><div class="road-brand-left">'
        '<div class="road-logo" aria-hidden="true">S</div>'
        '<div><div class="road-brand-name">Smart Road</div>'
        '<div class="road-brand-meta">Road intelligence studio</div></div></div>'
        '<span class="road-state">● Vision analysis</span></div>',
        unsafe_allow_html=True,
    )


def hero(title, subtitle, *, kicker="Smart Road / Video intelligence", footer=""):
    st.markdown(
        '<div class="road-hero"><div class="road-kicker">' + _safe(kicker)
        + '</div><h1>' + _safe(title) + '</h1><p>' + _safe(subtitle)
        + '</p>' + ('<div class="road-hero-foot">' + _safe(footer) + '</div>' if footer else "")
        + '</div>', unsafe_allow_html=True,
    )


def section(title, subtitle="", kicker="Road intelligence"):
    st.markdown(
        '<div class="road-section"><div><div class="road-eyebrow">' + _safe(kicker)
        + '</div><h3>' + _safe(title) + '</h3>'
        + ('<p>' + _safe(subtitle) + '</p>' if subtitle else "")
        + '</div></div>', unsafe_allow_html=True,
    )


def metrics(items):
    parts = ['<div class="road-metric-grid">']
    for label, value, help_text in items:
        parts.append('<div class="road-metric"><div class="k">' + _safe(label)
                     + '</div><div class="v">' + _safe(value)
                     + '</div><div class="h">' + _safe(help_text) + '</div></div>')
    parts.append('</div>')
    st.markdown("".join(parts), unsafe_allow_html=True)


def legend():
    st.markdown(
        '<div class="road-legend" aria-label="Proximity overlay color key">'
        '<span><i style="background:#7188a4"></i>Unmeasured</span>'
        '<span><i style="background:#3aab78"></i>Measured spacing</span>'
        '<span><i style="background:#edbd45"></i>Review / caution</span>'
        '<span><i style="background:#ed813b"></i>Close approach</span>'
        '<span><i style="background:#dc4650"></i>Very close</span>'
        '</div>', unsafe_allow_html=True,
    )


def notice(message):
    st.markdown('<div class="road-notice">' + _safe(message) + '</div>',
                unsafe_allow_html=True)


def issue(title, description, *, level="caution", label="Needs review", evidence="", action=""):
    level = level if level in {"safe", "caution", "risk", "critical", "unknown"} else "unknown"
    markup = (
        '<div class="road-issue-card" data-level="' + level + '">'
        '<div class="road-card-top"><div class="road-card-title">' + _safe(title)
        + '</div><span class="road-pill" data-level="' + level + '">'
        + _safe(label) + '</span></div><div class="road-card-copy">'
        + _safe(description) + '</div>'
    )
    if evidence:
        markup += '<div class="road-card-meta">' + _safe(evidence) + '</div>'
    if action:
        markup += '<div class="road-card-action"><strong>Next step:</strong> ' + _safe(action) + '</div>'
    st.markdown(markup + '</div>', unsafe_allow_html=True)


def recommendation(recommendation):
    title = recommendation.get("title", "Review finding")
    priority = recommendation.get("priority", "Review")
    evidence = recommendation.get("evidence", "")
    reason = recommendation.get("reason", "")
    action = recommendation.get("action", "")
    verify = recommendation.get("verify", "")
    st.markdown(
        '<div class="road-reco-card">'
        '<div class="road-card-top"><div class="road-card-title">' + _safe(title)
        + '</div><span class="road-pill" data-level="unknown">' + _safe(priority) + '</span></div>'
        '<div class="road-card-copy">' + _safe(reason) + '</div>'
        '<div class="road-card-meta"><strong>Observed:</strong> ' + _safe(evidence) + '</div>'
        '<div class="road-card-action"><strong>Suggested next step:</strong> ' + _safe(action) + '</div>'
        '<div class="road-card-meta"><strong>Verify on site:</strong> ' + _safe(verify) + '</div></div>',
        unsafe_allow_html=True,
    )

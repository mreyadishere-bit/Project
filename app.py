"""Smart Road MVP educational dashboard in Arabic."""
from pathlib import Path
import tempfile
import os
import pandas as pd
import streamlit as st
from database import init_db, fetch, add_report, add_analysis
from routes import best_route, EDGES
from weather import current_weather

HOSTED = os.environ.get("SMART_ROAD_HOSTED", "0") == "1"

st.set_page_config(page_title="Smart Road AI | Road Intelligence Lab", page_icon="🛣️", layout="wide")
if HOSTED:
    from video_ui import video_tab
    video_tab()
    st.stop()
if not HOSTED:
    init_db()

st.markdown('''<style>
.block-container {padding-top: 1.6rem; max-width: 1150px;}
h1,h2,h3 {letter-spacing: -0.025em;}
div[data-testid="stMetric"] {border: 1px solid #dce3e9; border-radius: 14px; padding: 14px;}
.stAlert {border-radius: 12px;}
</style>''', unsafe_allow_html=True)

st.title("🚦 Smart Road — Video Intelligence v2")
st.caption("تحليل فيديو طويل وتتبّع مباشر محليًا + بلاغات وخريطة وطقس وحساسات تجريبية")

st.info("⚠️ هذه نسخة بحثية تجريبية، وليست نظام إنذار معتمدًا. مؤشر الفيديو لا يمثل احتمال وقوع حادث، ولا يُستخدم لاتخاذ قرار قيادة.")

with st.sidebar:
    st.header("📍 موقع التجربة")
    latitude = st.number_input("خط العرض", -90.0, 90.0, 30.0444, format="%.5f")
    longitude = st.number_input("خط الطول", -180.0, 180.0, 31.2357, format="%.5f")
    st.caption("الإحداثيات الافتراضية لوسط القاهرة للتجربة فقط. غيّرها يدويًا لمكان تصوير الفيديو أو البلاغ.")
    st.markdown("---")
    st.caption("كل البلاغات والنتائج مخزنة على جهازك في smart_road.sqlite3. لا يوجد تسجيل دخول أو نشر عام.")

vtab, reporttab, maptab, weathertab, routetab, sensortab = st.tabs([
    "🎬 تحليل الفيديو", "📝 بلاغ جديد", "🗺️ الخريطة والبيانات", "🌦️ الطقس", "🛣️ مقارنة الطرق", "📡 الحساسات"
])

with vtab:
    from video_ui import video_tab
    video_tab()

with reporttab:
    st.subheader("بلاغ مواطن تجريبي")
    with st.form("report"):
        issue = st.selectbox("المشكلة", ["حفرة", "تجمع مياه", "ضعف إنارة", "عائق", "منطقة رؤية محجوبة", "أخرى"])
        severity = st.selectbox("درجة الأولوية التي يبلغ عنها المواطن (غير مؤكدة)", ["منخفضة", "متوسطة", "مرتفعة"])
        description = st.text_area("وصف المشكلة", placeholder="مثلًا: حفرة قرب مدخل الشارع...")
        st.caption(f"موقع البلاغ حاليًا: {latitude:.5f}, {longitude:.5f} (غيّره من الشريط الجانبي)")
        saved = st.form_submit_button("إرسال البلاغ", type="primary")
    if saved:
        if not description.strip():
            st.warning("اكتب وصفًا قبل الإرسال.")
        else:
            add_report(issue, severity, description, latitude, longitude)
            st.success("اتحفظ البلاغ محليًا وظهر في الخريطة.")

with maptab:
    st.subheader("خريطة البلاغات وملخصات التحليل")
    reports = fetch("reports")
    analyses = fetch("analyses")
    mr, ma = st.columns(2)
    mr.metric("بلاغات محفوظة", len(reports))
    ma.metric("فيديوهات تم تحليلها", len(analyses))
    markers = [{"lat": r["latitude"], "lon": r["longitude"]} for r in reports]
    markers += [{"lat": a["latitude"], "lon": a["longitude"]} for a in analyses]
    if markers:
        st.map(pd.DataFrame(markers), latitude="lat", longitude="lon", zoom=10)
        st.caption("الخريطة تعرض مواقع أدخلها المستخدم، ولا تستنتج موقع الفيديو آليًا. النقاط ليست مخاطر مؤكدة.")
    else:
        st.info("لا توجد بيانات بعد. أضف بلاغًا أو حلل فيديو أولًا.")
    if reports:
        st.markdown("**بلاغات المواطنين**")
        st.dataframe(pd.DataFrame(reports), use_container_width=True, hide_index=True)
    if analyses:
        st.markdown("**ملخصات الفيديو**")
        st.dataframe(pd.DataFrame(analyses), use_container_width=True, hide_index=True)

with weathertab:
    st.subheader("قراءة الطقس الحالي من Open-Meteo")
    st.caption("الطقس الحالي في الإحداثيات المدخلة. غير مرتبط بزمن تصوير فيديو قديم، ولا يثبت تأثير الطقس على حادث.")
    if st.button("🌤️ جلب الطقس الحالي"):
        try:
            w = current_weather(latitude, longitude)
            t, r, wind = st.columns(3)
            t.metric("الحرارة", f"{w['temperature_2m']} °C")
            r.metric("الأمطار الحالية", f"{w['precipitation']} mm")
            wind.metric("سرعة الرياح", f"{w['wind_speed_10m']} km/h")
            st.write(f"الوقت المحلي للخدمة: {w.get('time', 'غير متاح')} — كود الطقس: {w.get('weather_code', '—')}")
            st.caption("مصدر الطقس: Open-Meteo.com")
        except Exception as e:
            st.error(f"تعذر جلب الطقس الآن: {e}")

with routetab:
    st.subheader("كيف يمكن تفضيل الأمان على أقصر مسافة؟")
    st.warning("🧪 هذه شبكة طرق افتراضية بأوزان خطر مخترعة للشرح فقط؛ لا تقدم إرشادات ملاحة حقيقية.")
    st.dataframe(pd.DataFrame(EDGES, columns=["من", "إلى", "المسافة (كم)", "خطر توضيحي 0-1"]),
                 hide_index=True, use_container_width=True)
    short_path, short_km, short_exposure = best_route(safety_weight=0)
    safe_path, safe_km, safe_exposure = best_route(safety_weight=4)
    a, b = st.columns(2)
    with a:
        st.markdown("**أقصر مسافة**")
        st.write(" ← ".join(short_path))
        st.write(f"المسافة: {short_km} كم | مجموع التعرض التوضيحي: {short_exposure:.2f}")
    with b:
        st.markdown("**المسار الأقل تكلفة بعد وزن الأمان**")
        st.write(" ← ".join(safe_path))
        st.write(f"المسافة: {safe_km} كم | مجموع التعرض التوضيحي: {safe_exposure:.2f}")
    st.code("route_cost = distance_km × (1 + safety_weight × illustrative_risk)", language="text")

with sensortab:
    st.subheader("قراءات نموذج الطريق بالحساسات (اختياري)")
    data = fetch("sensor_readings")
    st.caption("لو شبكت ESP32 بالـ Wi-Fi وشغّلت receiver.py، القراءات هتتحفظ هنا. اضغط تحديث لقراءة أحدث بيانات.")
    if st.button("🔄 تحديث القراءات"):
        st.rerun()
    if data:
        first = data[0]
        a, b = st.columns(2)
        a.metric("آخر قراءة للإضاءة (ADC خام)", first["light_raw"])
        b.metric("هل الحساس اكتشف عائقًا؟", "نعم" if first["obstacle"] else "لا")
        st.caption("ADC ليس قياس لوكس، واستشعار العائق قائم على مدى حساس قصير وليس اكتشاف حفرة أو تصادم حقيقي.")
        st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
    else:
        st.info("لا توجد قراءات حساسات حتى الآن. البرنامج يعمل دون أي هاردوير.")

st.divider()
st.caption("Educational proof of concept • Not a certified safety system • Ultralytics AGPL-3.0 • Weather: Open-Meteo")

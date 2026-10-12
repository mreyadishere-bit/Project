"""Streamlit video intelligence tab, usable on a Windows local machine."""
from pathlib import Path
import shutil
import uuid
import os

import pandas as pd
import streamlit as st
from video_engine import VideoJob, VideoSettings, OUTPUTS


STATUS_AR = {
    "starting": "جاري البدء", "loading model": "تحميل نموذج AI", "running": "التحليل جارٍ",
    "stopped": "أُوقف بناءً على طلبك", "completed": "اكتمل التحليل", "error": "خطأ",
}


def save_uploaded_video(file):
    folder = OUTPUTS / "uploads"
    folder.mkdir(parents=True, exist_ok=True)
    extension = Path(file.name).suffix.lower()
    if extension not in {".mp4", ".avi", ".mov", ".mkv", ".m4v"}:
        raise ValueError("اختار ملف فيديو MP4 أو AVI أو MOV أو MKV")
    name = f"{uuid.uuid4().hex}{extension}"
    dest = folder / name
    try:
        file.seek(0)
        with dest.open("wb") as output:
            shutil.copyfileobj(file, output, length=8 * 1024 * 1024)
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    return dest


def video_tab():
    st.subheader("🎬 Video Intelligence — تحليل وتتبّع مباشر")
    st.caption("حلّل فيديو لساعات، أو استخدم كاميرا اللابتوب في الوقت الفعلي. النتائج تظهر أثناء التحليل وتُحفظ محليًا.")
    st.warning("⚠️ التحليل تجريبي. اتجاه الحركة اتجاه داخل الصورة فقط، والـ Track IDs قد تتغير عند اختفاء الأجسام. لا يوجد قياس سرعة حقيقية، كشف حفر، أو تنبؤ حوادث معتمد.")

    hosted = os.environ.get("SMART_ROAD_HOSTED", "0") == "1"
    if hosted:
        st.info("🌐 النسخة المستضافة تدعم رفع الفيديو للتحليل. مسارات الهارد وكاميرا اللابتوب غير متاحة عبر سيرفر بعيد؛ البث من المتصفح يحتاج WebRTC وسنضيفه لاحقًا.")
    current = st.session_state.get("video_job")
    running = current is not None and current.snapshot()["status"] in {"starting", "loading model", "running"}
    source_options = (["⬆️ رفع فيديو صغير/متوسط"] if hosted else [
        "📁 ملف موجود على اللابتوب (مُفضّل للفيديوهات الكبيرة)",
        "⬆️ رفع فيديو صغير/متوسط", "📷 كاميرا اللابتوب Live"])
    source_mode = st.radio("مصدر الفيديو", source_options,
                           horizontal=True, disabled=running, key="video_source_mode")
    source: str | int | None = None
    name = ""
    uploaded = None
    if source_mode.startswith("📁"):
        path = st.text_input("المسار الكامل للفيديو على نفس الكمبيوتر المشغّل للموقع", placeholder=r"C:\Users\YourName\Videos\road.mp4", disabled=running,
                             help='من File Explorer: Shift + Right Click على الفيديو ثم Copy as path والصق المسار هنا.')
        source = path.strip().strip('"')
        name = Path(source).name if source else ""
        st.caption("هنا مفيش حد للرفع أصلًا: البرنامج بيقرأ الملف مباشرة من الهارد. تقدر تحلّل ساعات، حسب سرعة جهازك والمساحة المتاحة.")
    elif source_mode.startswith("⬆️"):
        uploaded = st.file_uploader("ارفع فيديو", type=["mp4", "avi", "mov", "mkv", "m4v"], key="advanced_video_upload", disabled=running)
        if uploaded:
            name = uploaded.name
            st.caption(f"حجم الملف: {uploaded.size / 1024**2:.1f} MB. الفيديوهات الكبيرة جدًا: استخدم مسار الملف بدل الرفع لتقليل استهلاك الذاكرة.")
    else:
        source = int(st.selectbox("رقم الكاميرا", [0, 1, 2], disabled=running,
                                 help="0 الكاميرا الأساسية. دي كاميرا اللابتوب اللي بيشغّل البرنامج، مش كاميرا الهاتف أو المتصفح على جهاز آخر."))
        name = f"webcam-{source}"
        st.caption("البث مباشر من كاميرا اللابتوب الموصولة بالبرنامج. جرّب رقم 1 لو 0 مش شغال. اقفل Zoom/Teams لو ماسكين الكاميرا.")

    with st.expander("⚙️ إعدادات الدقة والأداء", expanded=not running):
        c1, c2, c3 = st.columns(3)
        with c1:
            model = st.selectbox("حجم نموذج YOLO", ["yolo26n.pt", "yolo26s.pt", "yolo26m.pt"],
                                 format_func=lambda v: {"yolo26n.pt": "Nano — أسرع", "yolo26s.pt": "Small — متوازن", "yolo26m.pt": "Medium — أثقل"}[v], disabled=running)
            confidence = st.slider("أقل ثقة للكشف", 0.10, 0.90, 0.35, 0.05, disabled=running)
        with c2:
            fps = st.select_slider("عدد الإطارات المستهدفة في كل ثانية من الفيديو", [1, 2, 5, 10, 15, 30], value=5, disabled=running,
                                   help="في الملف يتم تحليل إطار كل مدة تقريبية. كاميرا Live تعمل بأقصى سرعة تحليل ممكنة على جهازك.")
            image_size = st.selectbox("حجم صورة AI", [416, 512, 640, 960], index=2, disabled=running)
        with c3:
            all_classes = st.checkbox("اكتشاف جميع أنواع YOLO (مش المرور فقط)", value=False, disabled=running)
            export_video = st.checkbox("احفظ نسخة فيديو عليها المربعات (قد تكون ضخمة)", value=False,
                                       disabled=running or source_mode.startswith("📷"))
        st.caption("Nano و5 FPS هي البداية المناسبة لمعظم اللابتوبات. رفع FPS أو حجم النموذج هيزيد الدقة الزمنية المحتملة لكن هيبطّأ التحليل. البرنامج يقرأ الفيديو كله حتى لو بيحلل عينات منه.")

    col_start, col_hint = st.columns([1, 2])
    with col_start:
        if st.button("▶️ ابدأ التحليل", type="primary", disabled=running, use_container_width=True):
            try:
                if source_mode.startswith("📁"):
                    if not source or not Path(source).is_file():
                        raise ValueError("المسار غلط أو الملف مش موجود. استخدم Copy as path من مستكشف الملفات.")
                    if Path(source).suffix.lower() not in {".mp4", ".mov", ".avi", ".mkv", ".m4v"}:
                        raise ValueError("صيغة غير مدعومة. جرّب MP4.")
                    actual_source = str(Path(source).resolve())
                elif source_mode.startswith("⬆️"):
                    if uploaded is None:
                        raise ValueError("اختار فيديو أولًا.")
                    with st.spinner("جاري نسخ الملف للتخزين المحلي..."):
                        actual_source = str(save_uploaded_video(uploaded))
                else:
                    actual_source = source
                settings = VideoSettings(model_name=model, confidence=confidence,
                                         image_size=image_size, analysis_fps=fps,
                                         all_classes=all_classes,
                                         save_video=bool(export_video and not isinstance(actual_source, int)))
                st.session_state["video_job"] = VideoJob(actual_source, settings, label=name)
                st.rerun()
            except Exception as e:
                st.error(f"تعذر البدء: {e}")
    with col_hint:
        if not running:
            st.caption("ابدأ ملفًا جديدًا بعد اكتمال التحليل أو إيقاف التشغيل السابق. لا تقفل البرنامج أثناء التشغيل.")
        else:
            st.caption("التحليل شغّال في الخلفية. تقدر تتابع العرض أو تضغط إيقاف، وتصدّر النتائج بعد الإنهاء.")

    # fragment polls state without blocking the Streamlit UI; built-in since 1.37.
    @st.fragment(run_every=1.0 if running else None)
    def live_results():
        job = st.session_state.get("video_job")
        if job is None:
            st.info("اختار فيديو أو الكاميرا، واضغط ابدأ التحليل.")
            return
        snap = job.snapshot()
        st.divider()
        left, middle, right = st.columns([2, 1, 1])
        left.markdown(f"**الحالة:** {STATUS_AR.get(snap['status'], snap['status'])}  |  **المصدر:** {snap['label']}")
        middle.caption(f"المعالجة: {snap['device']}")
        right.caption(f"مجلد النتائج: outputs/{job.id}")
        if snap["error"]:
            st.error(snap["error"])
        if not snap["is_camera"]:
            if snap["duration_seconds"]:
                fraction = min(1.0, snap["frames_read"] / snap["total_frames"]) if snap["total_frames"] else min(1.0, snap["video_second"] / snap["duration_seconds"])
                st.progress(fraction, text=f"وصل إلى {snap['video_second'] / 60:.1f} من {snap['duration_seconds'] / 60:.1f} دقيقة — {fraction:.1%}")
            elif snap["analyzed_frames"]:
                st.caption(f"مدة الفيديو غير معروفة؛ تم تحليل حتى الثانية {snap['video_second']:.1f}")
        a,b,c,d = st.columns(4)
        counts = snap["detected_now"]
        a.metric("مركبات في آخر إطار", counts.get("vehicles", 0))
        b.metric("أشخاص في آخر إطار", counts.get("people", 0))
        c.metric("معرفات مسارات ظهرت", snap["unique_tracks"])
        d.metric("إطارات محللة / ثانية تشغيل", f"{snap['processing_fps']:.1f}")
        st.caption(f"تم تحليل {snap['analyzed_frames']:,} إطارًا | أقصى مركبات في إطار: {snap['max_vehicles']} | أقصى أشخاص في إطار: {snap['max_people']}. معرفات المسارات تقديرية وقد يتغير ID لنفس الشخص أو السيارة.")
        if snap["preview_jpeg"]:
            st.image(snap["preview_jpeg"], caption=f"أحدث إطار محلل — عند {snap['video_second']:.1f} ثانية من المصدر", use_container_width=True)
        else:
            st.info("في انتظار أول إطار... تنزيل نموذج YOLO أول مرة قد يستغرق وقتًا.")
        if snap["status"] in {"starting", "loading model", "running"}:
            control1, control2 = st.columns(2)
            if not snap["is_camera"]:
                with control1:
                    if st.button("▶️ استكمال" if snap["paused"] else "⏸️ إيقاف مؤقت", key="pause_video_btn", use_container_width=True):
                        job.resume() if snap["paused"] else job.pause()
                        st.rerun(scope="fragment")
            with control2:
                if st.button("⏹️ إيقاف التحليل", key="stop_video_btn", use_container_width=True):
                    job.stop()
                    st.rerun(scope="fragment")
        if snap["recent_frames"]:
            st.markdown("**📈 الأجسام المكتشفة عبر الزمن (آخر 180 إطارًا محللًا)**")
            df = pd.DataFrame(snap["recent_frames"])
            st.line_chart(df.set_index("video_second")[["vehicles", "people", "traffic_lights", "stop_signs"]])
        if snap["recent_objects"]:
            st.markdown("**🔎 التفاصيل لكل جسم (آخر 80 عملية رصد)**")
            st.dataframe(pd.DataFrame(snap["recent_objects"])[["video_second", "track_id", "class", "confidence", "center_x", "center_y", "direction"]].iloc[::-1],
                         use_container_width=True, hide_index=True)
        if snap["status"] in {"completed", "stopped", "error"}:
            st.markdown("**📂 ملفات النتيجة محفوظة على جهازك**")
            for file_path, label in [(job.summary_file, "إحصاءات كل إطار"), (job.objects_file, "تفاصيل كل جسم"), (job.video_file, "الفيديو الناتج")]:
                if file_path.is_file() and file_path.stat().st_size > 0:
                    mb = file_path.stat().st_size / (1024 * 1024)
                    st.write(f"{label}: `{file_path}` ({mb:.1f} MB)")
                    if mb <= 25:
                        st.download_button(f"⬇️ تحميل {label}", data=file_path.read_bytes(), file_name=f"{job.id}_{file_path.name}",
                                           mime="video/mp4" if file_path.suffix == ".mp4" else "text/csv", key=f"dl_{job.id}_{file_path.name}")
                    else:
                        st.caption("الملف كبير؛ افتحه من المسار على جهازك بدل تحميله من المتصفح.")
            st.caption("كله محلي، لا يوجد رفع إلى سحابة. ملفات outputs لا تُحذف تلقائيًا؛ احذف النتائج القديمة بنفسك لتوفير المساحة.")

    live_results()

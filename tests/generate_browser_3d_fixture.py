"""Generate deterministic standalone browser fixture for the ACTUAL 3D frontend."""
from pathlib import Path
import base64
import json
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from traffic_control_sim import ControlInputs,simulate
from traffic_control_view import VIEW_HTML

if __name__=="__main__":
    target=Path(sys.argv[1]);target.parent.mkdir(parents=True,exist_ok=True)
    report=simulate(ControlInputs(seconds=60,seed=88,vehicles_per_hour=480,pedestrians_per_hour=240))
    generated_video=target.parent/"original-source.mp4"
    subprocess.run([
        "ffmpeg","-hide_banner","-loglevel","error","-y",
        "-f","lavfi","-i","testsrc2=size=480x270:rate=12:duration=5",
        "-an","-c:v","libx264","-pix_fmt","yuv420p",
        "-preset","ultrafast","-crf","34","-movflags","+faststart",
        str(generated_video)
    ],check=True,timeout=35)
    video_uri="data:video/mp4;base64,"+base64.b64encode(generated_video.read_bytes()).decode("ascii")
    html=VIEW_HTML.replace("__SOURCE__",video_uri).replace(
        "__DATA__",json.dumps(report,separators=(",",":")).replace("</","<\\/"))
    target.write_text(html,encoding="utf-8")
    print(f"3D browser fixture prepared: {target} ({target.stat().st_size:,} bytes)")

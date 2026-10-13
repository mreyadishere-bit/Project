"""Generate deterministic standalone browser fixture for the ACTUAL 3D frontend."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from traffic_control_sim import ControlInputs,simulate
from traffic_control_view import VIEW_HTML

if __name__=="__main__":
    target=Path(sys.argv[1]);target.parent.mkdir(parents=True,exist_ok=True)
    report=simulate(ControlInputs(seconds=60,seed=88,vehicles_per_hour=480,pedestrians_per_hour=240))
    html=VIEW_HTML.replace("__SOURCE__","").replace(
        "__DATA__",json.dumps(report,separators=(",",":")).replace("</","<\\/"))
    target.write_text(html,encoding="utf-8")
    print(f"3D browser fixture prepared: {target} ({target.stat().st_size:,} bytes)")

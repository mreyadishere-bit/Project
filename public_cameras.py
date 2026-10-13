"""Public agency camera sources for experimental, consent-respecting road analysis.

All URLs are pinned to agency-published HLS feeds, not supplied by visitors.
Feed availability can change and public availability is not a guarantee of
unrestricted reuse; display attribution and follow provider conditions.
"""
from __future__ import annotations
from urllib.parse import urlsplit
import ipaddress

CAMERAS = {
    "caltrans-sacramento-i5": {
        "label": "California · Sacramento · I-5 Pocket Road",
        "operator": "Caltrans (California Department of Transportation)",
        "stream_url": "https://wzmedia.dot.ca.gov/D3/5_Pocket_Rd_OC_SAC5_SB.stream/playlist.m3u8",
        "info_url": "https://cwwp2.dot.ca.gov/vm/streamlist.htm",
        "region": "Sacramento, California, USA",
        "rights_url": "https://dot.ca.gov/conditions-of-use",
    },
    "seattle-spokane-st": {
        "label": "Washington · Seattle · 11th Ave SW / Spokane St",
        "operator": "Seattle Department of Transportation",
        "stream_url": "https://58cc2dce193dd.streamlock.net/live/11_SW_Spokane_EW.stream/playlist.m3u8",
        "info_url": "https://www.seattle.gov/transportation/projects-and-programs/programs/technology-program/traffic-cameras",
        "region": "Seattle, Washington, USA",
        "rights_url": "https://www.seattle.gov/transportation",
    },
    "seattle-50th-st": {
        "label": "Washington · Seattle · 12th Ave NE / NE 50th St",
        "operator": "Seattle Department of Transportation",
        "stream_url": "https://58cc2dce193dd.streamlock.net/live/12_NE_50_EW.stream/playlist.m3u8",
        "info_url": "https://www.seattle.gov/transportation/projects-and-programs/programs/technology-program/traffic-cameras",
        "region": "Seattle, Washington, USA",
        "rights_url": "https://www.seattle.gov/transportation",
    },
}


def get_camera(source_id: str):
    """Resolve only a documented catalog camera ID (never arbitrary URLs)."""
    if not isinstance(source_id, str) or source_id not in CAMERAS:
        raise ValueError("Unknown public camera. Choose a listed camera from the catalog.")
    record = dict(CAMERAS[source_id])
    parsed = urlsplit(record["stream_url"])
    if parsed.scheme != "https" or parsed.hostname not in {
        "wzmedia.dot.ca.gov", "58cc2dce193dd.streamlock.net"
    } or not parsed.path.endswith(".m3u8"):
        raise RuntimeError("Public camera catalog failed host validation.")
    return record


def camera_choices():
    return {key: val["label"] for key, val in CAMERAS.items()}

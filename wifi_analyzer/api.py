"""FastAPI backend for the WiFi Debugger UI."""
from __future__ import annotations
import asyncio
import time
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .platform_layer import get_platform_backend
from .modules.speed_test import _measure_download, _measure_upload, _measure_latency
from .modules.channel_analyzer import ChannelAnalyzer
from .modules.diagnostics import DiagnosticsEngine
from .utils import dbm_to_quality, freq_to_band

import numpy as np
from scipy.interpolate import Rbf
from scipy.ndimage import gaussian_filter
from scipy.optimize import least_squares

app = FastAPI(title="WiFi Debugger API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global backend — initialised once
_backend = None
_interface = None


def _get_backend():
    global _backend, _interface
    if _backend is None:
        _backend = get_platform_backend()
        ifaces = _backend.get_wifi_interfaces()
        _interface = ifaces[0] if ifaces else None
    return _backend, _interface


# ------------------------------------------------------------------ #
# Models                                                               #
# ------------------------------------------------------------------ #

class CoveragePointIn(BaseModel):
    x: float
    y: float
    signal_dbm: int


class HeatmapRequest(BaseModel):
    room_w: float
    room_h: float
    points: list[CoveragePointIn]
    grid_resolution: int = 80


class LocateApRequest(BaseModel):
    room_w: float
    room_h: float
    points: list[CoveragePointIn]


# ------------------------------------------------------------------ #
# Endpoints                                                            #
# ------------------------------------------------------------------ #

@app.get("/api/interfaces")
def get_interfaces():
    backend, iface = _get_backend()
    return {"interfaces": backend.get_wifi_interfaces(), "active": iface}


@app.post("/api/interface/{name}")
def set_interface(name: str):
    global _interface
    _, _ = _get_backend()
    _interface = name
    return {"interface": name}


@app.get("/api/scan")
def scan_networks():
    backend, iface = _get_backend()
    if not iface:
        return JSONResponse(status_code=503, content={"error": "No WiFi interface"})
    aps = backend.scan_networks(iface)
    return {"networks": [
        {
            "ssid": a.ssid,
            "bssid": a.bssid,
            "channel": a.channel,
            "frequency_mhz": a.frequency_mhz,
            "band": a.band,
            "signal_dbm": a.signal_dbm,
            "quality": dbm_to_quality(a.signal_dbm),
            "max_rate_mbps": a.max_rate_mbps,
            "security": a.security,
            "is_connected": a.is_connected,
            "channel_width": a.channel_width,
        }
        for a in aps
    ]}


@app.get("/api/connection")
def get_connection():
    backend, iface = _get_backend()
    if not iface:
        return JSONResponse(status_code=503, content={"error": "No WiFi interface"})
    info = backend.get_connection_info(iface)
    if info is None:
        return {"connected": False}
    caps = backend.get_adapter_capabilities(iface)
    if info.driver == "Unknown":
        info.driver = caps.get("driver", "Unknown")
        info.vendor = caps.get("vendor", "Unknown")
    return {
        "connected": True,
        "ssid": info.ssid,
        "bssid": info.bssid,
        "interface": info.interface,
        "band": info.band,
        "channel": info.channel,
        "frequency_mhz": info.frequency_mhz,
        "signal_dbm": info.signal_dbm,
        "quality": dbm_to_quality(info.signal_dbm),
        "tx_rate_mbps": info.tx_rate_mbps,
        "rx_rate_mbps": info.rx_rate_mbps,
        "tx_power_dbm": info.tx_power_dbm,
        "power_management": info.power_management,
        "channel_width": info.channel_width,
        "mcs_index": info.mcs_index,
        "driver": info.driver,
        "driver_version": info.driver_version,
        "vendor": info.vendor,
        "retry_excessive": info.retry_excessive,
    }


@app.get("/api/signal")
def get_signal():
    backend, iface = _get_backend()
    if not iface:
        return {"signal_dbm": None}
    dbm = backend.get_signal_now(iface)
    return {"signal_dbm": dbm, "quality": dbm_to_quality(dbm)}


@app.get("/api/channels")
def get_channels():
    backend, iface = _get_backend()
    if not iface:
        return JSONResponse(status_code=503, content={"error": "No WiFi interface"})
    aps = backend.scan_networks(iface)
    analyzer = ChannelAnalyzer(backend, iface)
    report = analyzer._build_report(aps)

    # Serialize
    ch24 = []
    for ch in range(1, 14):
        count = len(report["ch24_aps"].get(ch, []))
        score = report["interference_24"].get(ch, 0)
        if count > 0 or score > 0:
            ch24.append({
                "channel": ch,
                "ap_count": count,
                "interference_score": round(score, 1),
                "is_current": any(a.is_connected and a.channel == ch for a in aps),
                "is_recommended": ch == report["best_24"],
            })

    ch5 = [
        {
            "channel": ch,
            "ap_count": len(ap_list),
            "is_current": any(a.is_connected and a.channel == ch for a in aps),
            "is_recommended": ch == report["best_5"],
        }
        for ch, ap_list in sorted(report["ch5_aps"].items())
    ]

    return {
        "band_24": ch24,
        "band_5": ch5,
        "recommended_24": report["best_24"],
        "recommended_5": report["best_5"],
    }


@app.get("/api/adapter")
def get_adapter():
    backend, iface = _get_backend()
    if not iface:
        return JSONResponse(status_code=503, content={"error": "No WiFi interface"})
    caps = backend.get_adapter_capabilities(iface)
    pm = backend.get_power_management_state(iface)
    return {**caps, "power_management": pm, "interface": iface}


@app.get("/api/diagnostics")
def get_diagnostics():
    backend, iface = _get_backend()
    if not iface:
        return JSONResponse(status_code=503, content={"error": "No WiFi interface"})
    engine = DiagnosticsEngine(backend, iface)
    aps = backend.scan_networks(iface)
    conn = backend.get_connection_info(iface)
    adapter = backend.get_adapter_capabilities(iface)

    findings = []
    if conn is None:
        findings.append({
            "severity": "critical", "category": "connection",
            "title": "Not Connected to WiFi",
            "detail": "No active WiFi connection detected.",
            "recommendation": "Connect to a WiFi network first.",
        })
    else:
        for f in (engine._check_band_selection(conn, aps, adapter) +
                  engine._check_power_management(conn) +
                  engine._check_signal_strength(conn) +
                  engine._check_channel_congestion(conn, aps) +
                  engine._check_tx_retries(conn) +
                  engine._check_channel_width(conn, aps) +
                  engine._check_same_ssid_bands(aps) +
                  engine._check_driver(adapter)):
            findings.append({
                "severity": f.severity,
                "category": f.category,
                "title": f.title,
                "detail": f.detail,
                "recommendation": f.recommendation,
            })

    if not findings:
        findings.append({
            "severity": "ok", "category": "general",
            "title": "All checks passed",
            "detail": "No issues detected with your WiFi configuration.",
            "recommendation": "Your WiFi setup looks healthy.",
        })

    critical = sum(1 for f in findings if f["severity"] == "critical")
    warnings = sum(1 for f in findings if f["severity"] == "warning")
    return {"findings": findings, "critical": critical, "warnings": warnings}


@app.post("/api/speedtest")
async def run_speedtest():
    loop = asyncio.get_event_loop()
    latency_ms, jitter_ms = await loop.run_in_executor(None, _measure_latency)
    download_mbps = 0.0
    from .modules.speed_test import DOWNLOAD_URLS, UPLOAD_URL
    for url in DOWNLOAD_URLS:
        dl = await loop.run_in_executor(None, _measure_download, url)
        if dl > 0:
            download_mbps = dl
            break
    upload_mbps = await loop.run_in_executor(None, _measure_upload, UPLOAD_URL)
    return {
        "download_mbps": round(download_mbps, 1),
        "upload_mbps": round(upload_mbps, 1),
        "latency_ms": latency_ms,
        "jitter_ms": jitter_ms,
    }


@app.post("/api/coverage/heatmap")
def generate_heatmap(req: HeatmapRequest):
    """Interpolate coverage points and return grid data for Plotly 3D surface."""
    if len(req.points) < 3:
        return JSONResponse(status_code=400, content={"error": "Need at least 3 points"})

    xs = np.array([p.x for p in req.points])
    ys = np.array([p.y for p in req.points])
    zs = np.array([p.signal_dbm for p in req.points], dtype=float)

    res = req.grid_resolution
    xi = np.linspace(0, req.room_w, res)
    yi = np.linspace(0, req.room_h, res)
    grid_x, grid_y = np.meshgrid(xi, yi)

    rbf = Rbf(xs, ys, zs, function="multiquadric", smooth=0.5)
    grid_z = rbf(grid_x, grid_y)
    grid_z = np.clip(grid_z, -100, -30)
    grid_z = gaussian_filter(grid_z, sigma=2)

    return {
        "x": xi.tolist(),
        "y": yi.tolist(),
        "z": grid_z.tolist(),
        "points": [{"x": p.x, "y": p.y, "signal_dbm": p.signal_dbm} for p in req.points],
        "room_w": req.room_w,
        "room_h": req.room_h,
        "vmin": -95,
        "vmax": -35,
    }


@app.post("/api/coverage/locate_ap")
def locate_ap(req: LocateApRequest):
    """Estimate the router/AP position from signal readings.

    Fits a log-distance path-loss model RSSI(d) = A - 10*n*log10(d) where the
    unknowns are the AP coordinates (ax, ay), the reference power A (RSSI at
    1 m) and the path-loss exponent n. Solved with bounded least-squares from
    several starting positions to avoid local minima.
    """
    if len(req.points) < 4:
        return JSONResponse(status_code=400, content={
            "error": "Need at least 4 measurement points to triangulate the router"})

    xs = np.array([p.x for p in req.points])
    ys = np.array([p.y for p in req.points])
    rssi = np.array([p.signal_dbm for p in req.points], dtype=float)

    # The router may sit just outside the measured room (e.g. next room)
    mx, my = req.room_w * 0.4, req.room_h * 0.4

    def residuals(params):
        ax, ay, ref_a, n = params
        d = np.sqrt((xs - ax) ** 2 + (ys - ay) ** 2)
        d = np.maximum(d, 0.3)  # avoid log blow-up at the AP itself
        return (ref_a - 10.0 * n * np.log10(d)) - rssi

    strongest = int(np.argmax(rssi))
    starts = [
        (float(xs[strongest]), float(ys[strongest])),
        (req.room_w / 2, req.room_h / 2),
        (0.0, 0.0), (req.room_w, 0.0), (0.0, req.room_h), (req.room_w, req.room_h),
    ]
    a0 = float(min(-25.0, max(-55.0, rssi.max() + 5)))

    best = None
    for sx, sy in starts:
        try:
            res = least_squares(
                residuals,
                x0=[sx, sy, a0, 2.5],
                bounds=([-mx, -my, -60.0, 1.5],
                        [req.room_w + mx, req.room_h + my, -15.0, 5.0]),
            )
        except Exception:
            continue
        if best is None or res.cost < best.cost:
            best = res

    if best is None:
        return JSONResponse(status_code=500, content={"error": "Optimization failed"})

    ax, ay, ref_a, n = best.x
    rmse = float(np.sqrt(np.mean(best.fun ** 2)))
    confidence = "high" if rmse < 2.5 else "medium" if rmse < 5.0 else "low"
    outside = ax < 0 or ay < 0 or ax > req.room_w or ay > req.room_h

    return {
        "x": round(float(ax), 2),
        "y": round(float(ay), 2),
        "clamped_x": round(float(np.clip(ax, 0, req.room_w)), 2),
        "clamped_y": round(float(np.clip(ay, 0, req.room_h)), 2),
        "outside_room": bool(outside),
        "rssi_at_1m": round(float(ref_a), 1),
        "path_loss_exponent": round(float(n), 2),
        "rmse_db": round(rmse, 2),
        "confidence": confidence,
        "points_used": len(req.points),
    }


@app.post("/api/power/fix")
async def fix_power_management():
    backend, iface = _get_backend()
    if not iface:
        return JSONResponse(status_code=503, content={"error": "No interface"})
    success = backend.set_power_management(iface, enabled=False)
    pm_now = backend.get_power_management_state(iface)
    return {"success": success, "power_management": pm_now}


# ------------------------------------------------------------------ #
# WebSocket — live signal stream                                       #
# ------------------------------------------------------------------ #

@app.websocket("/ws/signal")
async def ws_signal(websocket: WebSocket):
    await websocket.accept()
    backend, iface = _get_backend()
    try:
        while True:
            if iface:
                dbm = backend.get_signal_now(iface)
                await websocket.send_json({
                    "signal_dbm": dbm,
                    "quality": dbm_to_quality(dbm),
                    "timestamp": time.time(),
                })
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        pass


# ------------------------------------------------------------------ #
# Entry point                                                          #
# ------------------------------------------------------------------ #

def serve(host: str = "127.0.0.1", port: int = 7070):
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="warning")

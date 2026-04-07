import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory queues keyed by scan_id — one queue per active scan
_queues: dict[str, asyncio.Queue] = {}


def _get_queue(scan_id: str) -> asyncio.Queue:
    if scan_id not in _queues:
        _queues[scan_id] = asyncio.Queue()
    return _queues[scan_id]


async def send_progress(scan_id: str, phase: str, message: str, current: int, total: int):
    """Called by the pipeline to push progress messages to any connected WebSocket."""
    q = _get_queue(scan_id)
    await q.put({
        "phase": phase,
        "message": message,
        "current": current,
        "total": total,
    })


async def send_complete(scan_id: str, total_found: int, active_count: int):
    """Signal scan completion over the WebSocket."""
    q = _get_queue(scan_id)
    await q.put({
        "phase": "complete",
        "total_found": total_found,
        "active_count": active_count,
    })
    # Schedule queue cleanup after a short delay so the connected client has
    # time to receive the message before we drop the queue.
    import asyncio
    asyncio.get_event_loop().call_later(30, lambda: _queues.pop(scan_id, None))


async def send_error(scan_id: str, error: str):
    """Signal a scan failure over the WebSocket."""
    q = _get_queue(scan_id)
    await q.put({"phase": "error", "message": error})
    import asyncio
    asyncio.get_event_loop().call_later(30, lambda: _queues.pop(scan_id, None))


@router.websocket("/ws/scans/{scan_id}")
async def scan_websocket(websocket: WebSocket, scan_id: str):
    """Stream real-time scan progress to the frontend."""
    await websocket.accept()
    q = _get_queue(scan_id)

    try:
        while True:
            try:
                msg = await asyncio.wait_for(q.get(), timeout=60.0)
                await websocket.send_text(json.dumps(msg))

                if msg.get("phase") in ("complete", "error"):
                    break

            except asyncio.TimeoutError:
                # Keep-alive ping
                await websocket.send_text(json.dumps({"phase": "ping"}))

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for scan %s", scan_id)
    finally:
        # Only remove the queue when the scan is truly done (complete/error already
        # sent). If we remove it on every disconnect, messages sent by the pipeline
        # while no client is connected are lost, breaking reconnection.
        try:
            await websocket.close()
        except Exception:
            pass

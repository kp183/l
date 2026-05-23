"""AgentLens SDK Client for background batch span ingestion.
"""

from __future__ import annotations

import atexit
import logging
import queue
import threading
import time
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("agentlens")


class AgentLensClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "http://localhost:8000",
        debug: bool = False,
        enabled: bool = True,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.debug = debug
        self.enabled = enabled

        self._queue: queue.Queue[Dict[str, Any]] = queue.Queue(maxsize=10000)
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None

        if self.enabled:
            self.start()

    def start(self):
        if self._worker_thread is not None and self._worker_thread.is_alive():
            return
        self._stop_event.clear()
        self._worker_thread = threading.Thread(target=self._worker, daemon=True)
        self._worker_thread.start()

    def enqueue(self, item: Dict[str, Any]):
        if not self.enabled:
            return
        try:
            self._queue.put_nowait(item)
        except queue.Full:
            logger.warning("AgentLens queue full. Draining one item to make space.")
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except (queue.Empty, ValueError):
                pass
            try:
                self._queue.put_nowait(item)
            except queue.Full:
                pass  # Fail-safe

    def _safe_enqueue(self, item: Dict[str, Any]):
        try:
            self.enqueue(item)
        except Exception as e:
            if self.debug:
                logger.debug(f"Failed to enqueue span: {e}", exc_info=True)

    def _send_batch(self, batch: List[Dict[str, Any]]):
        if not batch:
            return
        try:
            url = f"{self.base_url}/v1/ingest"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            payload = {"spans": batch}

            # Sync request since we are on background worker thread
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(url, json=payload, headers=headers)
                if resp.status_code != 200:
                    if self.debug:
                        logger.debug(
                            f"Ingest failed with status {resp.status_code}: {resp.text}"
                        )
        except Exception as e:
            if self.debug:
                logger.debug(f"Error sending batch to AgentLens: {e}", exc_info=True)

    def _worker(self):
        while not self._stop_event.is_set():
            batch = []
            start_time = time.time()
            while len(batch) < 100:
                elapsed = time.time() - start_time
                if elapsed >= 0.5:
                    break
                timeout = 0.5 - elapsed
                try:
                    item = self._queue.get(timeout=timeout)
                    batch.append(item)
                except queue.Empty:
                    break

            if batch:
                self._send_batch(batch)
                for _ in range(len(batch)):
                    self._queue.task_done()
            else:
                time.sleep(0.05)

    def flush(self, timeout: float = 5.0):
        start_time = time.time()
        while not self._queue.empty():
            if time.time() - start_time > timeout:
                break
            batch = []
            while len(batch) < 100:
                try:
                    item = self._queue.get_nowait()
                    batch.append(item)
                except queue.Empty:
                    break
            if batch:
                self._send_batch(batch)
                for _ in range(len(batch)):
                    self._queue.task_done()
            else:
                break

    def stop(self, timeout: float = 5.0):
        self._stop_event.set()
        self.flush(timeout=timeout)
        if self._worker_thread is not None:
            self._worker_thread.join(timeout=timeout)

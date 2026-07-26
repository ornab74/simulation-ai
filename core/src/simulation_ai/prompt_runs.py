from __future__ import annotations

import json
import os
from pathlib import Path
from threading import RLock
from typing import Any

from .model import canonical_json, digest, utc_now


class PromptRunStoreError(ValueError):
    pass


class PromptRunStore:
    """Append-safe local store for non-authoritative model and workflow traces."""

    def __init__(self, home: Path) -> None:
        self.root = Path(home) / "prompt-runs"
        self.model_root = self.root / "model"
        self.workflow_root = self.root / "workflow"
        self.review_root = self.root / "reviews"
        self._lock = RLock()
        self.model_root.mkdir(parents=True, exist_ok=True)
        self.workflow_root.mkdir(parents=True, exist_ok=True)
        self.review_root.mkdir(parents=True, exist_ok=True)
        self._harden(self.root)
        self._harden(self.model_root)
        self._harden(self.workflow_root)
        self._harden(self.review_root)

    def save_model_run(self, record: dict[str, Any]) -> dict[str, Any]:
        return self._save(record, self.model_root, "nmsr.prompt-run/1", "run_id")

    def save_workflow_run(self, record: dict[str, Any]) -> dict[str, Any]:
        return self._save(record, self.workflow_root, "nmsr.prompt-workflow-run/1", "workflow_run_id")

    def load_model_run(self, run_id: str) -> dict[str, Any]:
        record = self._load_raw(self.model_root, run_id)
        review = self._latest_review(run_id)
        if review is None:
            return record
        if review.get("base_record_sha256") != record.get("record_sha256"):
            raise PromptRunStoreError(f"review base hash mismatch: {run_id}")
        view = dict(record)
        view["approval"] = dict(review["approval"])
        view["record_sha256"] = self._record_digest(view)
        return view

    def load_workflow_run(self, run_id: str) -> dict[str, Any]:
        return self._load_raw(self.workflow_root, run_id)

    def list_model_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        bounded = max(1, min(500, int(limit)))
        records: list[dict[str, Any]] = []
        for path in sorted(self.model_root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:bounded]:
            try:
                records.append(self.load_model_run(path.stem))
            except (OSError, json.JSONDecodeError, PromptRunStoreError):
                continue
        return records

    def list_workflow_runs(self, limit: int = 25) -> list[dict[str, Any]]:
        return self._list(self.workflow_root, limit)

    def review_model_run(
        self,
        run_id: str,
        *,
        decision: str,
        note: str = "",
        reviewed_by: str = "operator",
    ) -> dict[str, Any]:
        clean_decision = decision.strip().lower()
        if clean_decision not in {"approve", "reject", "needs-revision"}:
            raise PromptRunStoreError("decision must be approve, reject, or needs-revision")
        clean_note = note.strip()[:2000]
        clean_reviewer = reviewed_by.strip()[:120] or "operator"
        with self._lock:
            base = self._load_raw(self.model_root, run_id)
            reviewed_at = utc_now()
            approval = {
                "status": {
                    "approve": "approved-for-deterministic-review",
                    "reject": "rejected",
                    "needs-revision": "needs-revision",
                }[clean_decision],
                "reviewed_by": clean_reviewer,
                "note": clean_note,
                "reviewed_at": reviewed_at,
            }
            review = {
                "schema": "nmsr.prompt-run-operator-review/1",
                "run_id": run_id,
                "base_record_sha256": base.get("record_sha256", ""),
                "decision": clean_decision,
                "approval": approval,
                "commit_authority": False,
                "deterministic_gate_required": True,
                "created_at": reviewed_at,
            }
            review["review_sha256"] = digest(review)
            directory = self.review_root / run_id
            directory.mkdir(parents=True, exist_ok=True)
            self._harden(directory)
            self._atomic_write(directory / f"{review['review_sha256']}.json", review)
            return self.load_model_run(run_id)

    def _save(
        self,
        record: dict[str, Any],
        root: Path,
        schema: str,
        id_field: str,
    ) -> dict[str, Any]:
        if not isinstance(record, dict) or record.get("schema") != schema:
            raise PromptRunStoreError(f"{schema} record required")
        record_id = self._safe_id(str(record.get(id_field, "")))
        value = dict(record)
        value["commit_authority"] = False
        value["deterministic_gate_required"] = True
        value["record_sha256"] = self._record_digest(value)
        with self._lock:
            path = root / f"{record_id}.json"
            if path.exists():
                existing = self._load_raw(root, record_id)
                if existing.get("record_sha256") != value["record_sha256"]:
                    raise PromptRunStoreError(f"immutable run id collision: {record_id}")
                return existing
            self._atomic_write(path, value)
        return value

    def _load_raw(self, root: Path, record_id: str) -> dict[str, Any]:
        path = root / f"{self._safe_id(record_id)}.json"
        if not path.exists():
            raise PromptRunStoreError(f"prompt run not found: {record_id}")
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise PromptRunStoreError(f"invalid prompt run: {record_id}")
        return value

    def _latest_review(self, run_id: str) -> dict[str, Any] | None:
        directory = self.review_root / self._safe_id(run_id)
        if not directory.exists():
            return None
        values: list[dict[str, Any]] = []
        for path in directory.glob("*.json"):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(value, dict) and value.get("run_id") == run_id:
                expected = str(value.get("review_sha256", ""))
                unsigned = dict(value)
                unsigned.pop("review_sha256", None)
                if expected and digest(unsigned) == expected:
                    values.append(value)
        if not values:
            return None
        values.sort(key=lambda item: (str(item.get("created_at", "")), str(item.get("review_sha256", ""))))
        return values[-1]

    def _list(self, root: Path, limit: int) -> list[dict[str, Any]]:
        bounded = max(1, min(500, int(limit)))
        records: list[dict[str, Any]] = []
        for path in sorted(root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:bounded]:
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(value, dict):
                records.append(value)
        return records

    @staticmethod
    def _safe_id(value: str) -> str:
        if not value or len(value) > 96 or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for char in value):
            raise PromptRunStoreError("invalid prompt run id")
        return value

    @staticmethod
    def _record_digest(record: dict[str, Any]) -> str:
        value = dict(record)
        value.pop("record_sha256", None)
        return digest(value)

    @staticmethod
    def _harden(path: Path) -> None:
        try:
            os.chmod(path, 0o700)
        except OSError:
            pass

    @staticmethod
    def _atomic_write(path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        part = path.with_suffix(path.suffix + ".part")
        part.write_text(canonical_json(value), encoding="utf-8")
        try:
            os.chmod(part, 0o600)
        except OSError:
            pass
        part.replace(path)

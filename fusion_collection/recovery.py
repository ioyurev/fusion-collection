from __future__ import annotations

import contextlib
import csv
import json
import os
import shutil
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from typing import IO, TYPE_CHECKING, Final, TextIO

from fusion_common import (
    MeasurementManifest,
    MeasurementRecord,
    parse_csv_columns,
    save_fus,
    validate_manifest_dict,
)
from loguru import logger as log

from fusion_collection.config import APPDATA_PATH

if TYPE_CHECKING:
    from collections.abc import Sequence

RECOVERY_DIR_NAME: Final[str] = "recovery"
MANIFEST_FILENAME: Final[str] = "manifest.json"
DATA_FILENAME: Final[str] = "data.csv"
TARGET_FILENAME: Final[str] = "target.json"
FSYNC_INTERVAL_SEC: Final[float] = 10.0


def get_recovery_root(recovery_root: Path | None = None) -> Path:
    """Возвращает путь к каталогу незавершённых рабочих папок измерений в AppData."""
    return (
        recovery_root
        if recovery_root is not None
        else (APPDATA_PATH / RECOVERY_DIR_NAME)
    )


def _safe_slug(name: str) -> str:
    cleaned = "".join(
        ch if (ch.isalnum() or ch in ("-", "_")) else "_" for ch in name
    ).strip("_")
    return cleaned[:48] or "sample"


@dataclass(frozen=True)
class PendingSession:
    """Метаданные незавершённой рабочей папки измерения для восстановления."""

    staging_dir: Path
    target_path: Path | None
    sample: str
    operator: str
    row_count: int


def _write_manifest_file(staging_dir: Path, manifest: MeasurementManifest) -> None:
    manifest_path = staging_dir / MANIFEST_FILENAME
    tmp_path = staging_dir / f"{MANIFEST_FILENAME}.tmp"
    tmp_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    tmp_path.replace(manifest_path)


class StagingDirWriter:
    """Потоковый писатель рабочей папки измерения (manifest.json + data.csv + target.json)."""

    def __init__(
        self,
        staging_dir: Path,
        fh: TextIO,
        last_fsync: float,
    ) -> None:
        self.staging_dir = staging_dir
        self._fh: TextIO = fh
        self._writer = csv.writer(fh, lineterminator="\n")
        self._last_fsync: float = last_fsync
        self._closed: bool = False

    @classmethod
    def create(
        cls,
        recovery_root: Path,
        manifest: MeasurementManifest,
        columns: Sequence[str],
        target_path: Path | None = None,
    ) -> StagingDirWriter:
        """Создаёт рабочую папку в AppData, записывает manifest.json/target.json и открывает data.csv."""
        root = get_recovery_root(recovery_root)
        stamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S_%f")
        staging_dir = root / f"{stamp}_{_safe_slug(manifest.sample)}"
        staging_dir.mkdir(parents=True, exist_ok=True)
        _write_manifest_file(staging_dir, manifest)
        if target_path is not None:
            target_payload = json.dumps(
                {"target_path": str(target_path)},
                ensure_ascii=False,
                indent=2,
            )
            (staging_dir / TARGET_FILENAME).write_text(target_payload, encoding="utf-8")

        data_path = staging_dir / DATA_FILENAME
        fh: TextIO = data_path.open("w", encoding="utf-8", newline="", buffering=1)
        try:
            csv.writer(fh, lineterminator="\n").writerow(list(columns))
            fh.flush()
        except OSError:
            fh.close()
            raise
        return cls(staging_dir=staging_dir, fh=fh, last_fsync=time.monotonic())

    def update_manifest(self, manifest: MeasurementManifest) -> None:
        """Атомарно записывает актуальный manifest.json в рабочую папку."""
        _write_manifest_file(self.staging_dir, manifest)

    def append_row(self, row: Sequence[float]) -> None:
        """Дописывает строку данных в data.csv с построчным сбросом и периодическим fsync."""
        if self._closed:
            return
        self._writer.writerow(row)
        now = time.monotonic()
        if now - self._last_fsync >= FSYNC_INTERVAL_SEC:
            self._fh.flush()
            os.fsync(self._fh.fileno())
            self._last_fsync = now

    def close(self) -> None:
        """Сбрасывает и закрывает дескриптор data.csv без удаления рабочей папки."""
        if self._closed:
            return
        self._closed = True
        with contextlib.suppress(OSError):
            self._fh.flush()
            os.fsync(self._fh.fileno())
        with contextlib.suppress(OSError):
            self._fh.close()

    def cleanup(self) -> None:
        """Закрывает data.csv и удаляет рабочую папку измерения."""
        self.close()
        shutil.rmtree(self.staging_dir, ignore_errors=True)


def _read_clean_csv(csv_path: Path) -> tuple[str, int]:
    """Читает data.csv, отбрасывая неполные или повреждённые строки после сбоя."""
    if not csv_path.is_file():
        return "", 0

    raw_text = csv_path.read_text(encoding="utf-8", errors="replace")
    reader = csv.reader(StringIO(raw_text))
    header: list[str] | None = None
    for row in reader:
        if row:
            header = [col.strip() for col in row]
            break
    if not header:
        return "", 0

    expected_cols = len(header)
    buf = StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(header)
    valid_rows = 0
    dropped_rows = 0

    for row in reader:
        if not row:
            continue
        if len(row) != expected_cols:
            dropped_rows += 1
            continue
        try:
            for val_str in row:
                float(val_str.strip())
        except ValueError:
            dropped_rows += 1
            continue
        writer.writerow(row)
        valid_rows += 1

    if dropped_rows > 0:
        log.bind(path=str(csv_path), dropped_rows=dropped_rows).warning(
            "Discarded incomplete CSV rows while reading staging directory"
        )
    return buf.getvalue(), valid_rows


def _read_target_path(staging_dir: Path) -> Path | None:
    target_file = staging_dir / TARGET_FILENAME
    if not target_file.is_file():
        return None
    try:
        payload = json.loads(target_file.read_text(encoding="utf-8"))
        raw_path = payload.get("target_path")
        if isinstance(raw_path, str) and raw_path.strip():
            return Path(raw_path)
    except (OSError, ValueError):
        return None
    return None


def load_staging_dir(staging_dir: Path) -> MeasurementRecord:
    """Загружает рабочую папку (manifest.json + data.csv) в MeasurementRecord."""
    manifest_path = staging_dir / MANIFEST_FILENAME
    raw_dict = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest = validate_manifest_dict(raw_dict)

    clean_csv, row_count = _read_clean_csv(staging_dir / DATA_FILENAME)
    if row_count == 0:
        raise ValueError("В рабочей папке нет записанных точек измерения")
    data = parse_csv_columns(StringIO(clean_csv))
    return MeasurementRecord(
        manifest=manifest,
        data=data,
        source_format="FUS",
        source_version=manifest.schema_version,
    )


def pack_staging_dir_to_fus(
    staging_dir: Path,
    target: Path | IO[bytes],
) -> MeasurementRecord:
    """Превращает рабочую папку измерения в штатный контейнер .fus через fusion_common."""
    record = load_staging_dir(staging_dir)
    save_fus(record, target)
    return record


def remove_staging_dir(
    staging_dir: Path,
    *,
    remove_empty_target_stub: bool = False,
    target_path: Path | None = None,
) -> None:
    """Удаляет рабочую папку и при необходимости 1-байтовую пустую заглушку .fus."""
    if remove_empty_target_stub and target_path is not None:
        with contextlib.suppress(OSError):
            if target_path.is_file() and target_path.stat().st_size <= 1:
                target_path.unlink()
    shutil.rmtree(staging_dir, ignore_errors=True)


def _inspect_staging_entry(entry: Path) -> PendingSession | None:
    manifest_path = entry / MANIFEST_FILENAME
    if not manifest_path.is_file():
        return None
    try:
        raw_dict = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest = validate_manifest_dict(raw_dict)
        _, row_count = _read_clean_csv(entry / DATA_FILENAME)
    except (OSError, ValueError):
        return None
    if row_count == 0:
        return None
    return PendingSession(
        staging_dir=entry,
        target_path=_read_target_path(entry),
        sample=manifest.sample,
        operator=manifest.operator,
        row_count=row_count,
    )


def prune_invalid_sessions(
    recovery_root: Path | None = None,
    *,
    active_dir: Path | None = None,
) -> int:
    """Удаляет пустые и повреждённые рабочие папки в AppData/recovery и их 1-байтовые заглушки .fus."""
    root = get_recovery_root(recovery_root)
    if not root.is_dir():
        return 0
    active_resolved = active_dir.resolve() if active_dir is not None else None
    removed = 0

    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        if active_resolved is not None and entry.resolve() == active_resolved:
            continue
        if _inspect_staging_entry(entry) is None:
            target_path = _read_target_path(entry)
            log.bind(path=str(entry)).warning(
                "Removing empty or corrupted recovery directory"
            )
            remove_staging_dir(
                entry,
                remove_empty_target_stub=True,
                target_path=target_path,
            )
            removed += 1
    return removed


def find_pending_sessions(
    recovery_root: Path | None = None,
    *,
    active_dir: Path | None = None,
) -> list[PendingSession]:
    """Возвращает список восстановимых незавершённых рабочих папок без изменения файлов на диске."""
    root = get_recovery_root(recovery_root)
    if not root.is_dir():
        return []
    active_resolved = active_dir.resolve() if active_dir is not None else None
    pending: list[PendingSession] = []

    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        if active_resolved is not None and entry.resolve() == active_resolved:
            continue
        item = _inspect_staging_entry(entry)
        if item is not None:
            pending.append(item)
    return pending

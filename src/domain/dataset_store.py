"""In-process registry of uploaded dataframes, keyed by dataset_id (uuid).

Single-user local tool: dataframes are held in memory only, never persisted
(see spec/architecture.md § trust boundary). LRU-evicted beyond max_datasets.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

import pandas as pd

from config.settings import get_settings


@dataclass
class DatasetEntry:
    dataset_id: str
    dataframe: pd.DataFrame
    profile: dict
    sample: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class DatasetStore:
    def __init__(self, max_datasets: int) -> None:
        self._max = max_datasets
        self._entries: "OrderedDict[str, DatasetEntry]" = OrderedDict()
        self._lock = Lock()

    def add(self, dataframe: pd.DataFrame, profile: dict, sample: str) -> str:
        dataset_id = str(uuid4())
        entry = DatasetEntry(
            dataset_id=dataset_id, dataframe=dataframe, profile=profile, sample=sample
        )
        with self._lock:
            self._entries[dataset_id] = entry
            self._entries.move_to_end(dataset_id)
            while len(self._entries) > self._max:
                self._entries.popitem(last=False)  # evict least-recently-used
        return dataset_id

    def get(self, dataset_id: str) -> DatasetEntry | None:
        with self._lock:
            entry = self._entries.get(dataset_id)
            if entry is not None:
                self._entries.move_to_end(dataset_id)
            return entry

    def __contains__(self, dataset_id: str) -> bool:
        with self._lock:
            return dataset_id in self._entries

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)


_store: DatasetStore | None = None


def get_store() -> DatasetStore:
    global _store
    if _store is None:
        _store = DatasetStore(max_datasets=get_settings().max_datasets)
    return _store

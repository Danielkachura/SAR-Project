from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    repo_root: Path
    runtime_root: Path
    data_dir: Path



def build_config() -> AppConfig:
    repo_root = Path(__file__).resolve().parents[3]
    runtime_root = repo_root
    data_dir = runtime_root / "DATA"
    return AppConfig(repo_root=repo_root, runtime_root=runtime_root, data_dir=data_dir)

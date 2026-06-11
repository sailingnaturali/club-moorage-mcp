"""Load the bundled (or overridden) outstation data directory from disk."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from outstations_mcp.models import Club, Outstation


def data_path() -> Path:
    """Data directory from OUTSTATIONS_DATA_PATH, default the bundled package data."""
    env = os.environ.get("OUTSTATIONS_DATA_PATH")
    if env:
        return Path(env).expanduser()
    return Path(__file__).resolve().parent / "data"


@dataclass
class Store:
    root: Path
    outstations: list[Outstation]
    clubs: dict[str, Club]

    @classmethod
    def load(cls, root: Path | None = None) -> "Store":
        root = Path(root) if root is not None else data_path()
        # Both relationship types load into one list: RVYC-owned outstations under
        # outstations/, partner-club reciprocals under reciprocals/.
        outstations: list[Outstation] = []
        for sub in ("outstations", "reciprocals"):
            sub_dir = root / sub
            if sub_dir.is_dir():
                for md in sorted(sub_dir.rglob("*.md")):
                    outstations.append(Outstation.from_markdown(md.read_text(encoding="utf-8")))
        clubs: dict[str, Club] = {}
        club_dir = root / "clubs"
        if club_dir.is_dir():
            for md in sorted(club_dir.rglob("*.md")):
                c = Club.from_markdown(md.read_text(encoding="utf-8"))
                clubs[c.club] = c
        return cls(root=root, outstations=outstations, clubs=clubs)

    def get(self, name: str) -> Outstation | None:
        target = name.strip().casefold()
        for o in self.outstations:
            if o.name.casefold() == target:
                return o
        return None

    def get_club(self, club: str) -> Club | None:
        return self.clubs.get(club)

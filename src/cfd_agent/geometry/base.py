from pathlib import Path
from typing import Protocol
from cfd_agent.schemas import Geometry

class GeometryBuilder(Protocol):
    """Minimal extension point; MVP registers only the fixed mixing elbow."""
    def __call__(self, geometry: Geometry, output: Path) -> dict: ...

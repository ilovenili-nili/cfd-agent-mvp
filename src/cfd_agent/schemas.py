from typing import Literal
from pydantic import BaseModel, Field, model_validator, ConfigDict

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

class Geometry(StrictModel):
    diameter: float = Field(gt=0, description="Main internal diameter, m")
    branch_diameter: float = Field(gt=0)
    bend_radius: float = Field(gt=0, description="Centerline radius, m")
    inlet_length: float = Field(gt=0)
    outlet_length: float = Field(gt=0)
    branch_length: float = Field(gt=0)
    junction_angle: float = Field(default=60, ge=20, le=75)
    @model_validator(mode='after')
    def valid_bend(self):
        if self.bend_radius <= self.diameter / 2:
            raise ValueError('bend_radius must exceed diameter/2')
        if self.branch_diameter > self.diameter:
            raise ValueError('MVP branch diameter must not exceed main diameter')
        return self

class Inlet(StrictModel):
    velocity: float = Field(gt=0, description="m/s")
    temperature: float = Field(ge=273.15, le=373.15, description="K; single phase assumption requires pressure check")
    turbulence_intensity: float = Field(default=.05, gt=0, lt=1)

class Material(StrictModel):
    density: float = Field(default=998.2, gt=0)
    viscosity: float = Field(default=.001003, gt=0)
    specific_heat: float = Field(default=4182, gt=0)
    conductivity: float = Field(default=.6, gt=0)
    source: str = 'Illustrative room-temperature constants; verify against project handbook'
    reference_temperature: float = Field(default=293.15, ge=273.15, le=373.15)
    measured: bool = False

class Controls(StrictModel):
    mode: Literal['steady','transient'] = 'steady'
    model: Literal['laminar','sst'] = 'sst'
    mesh_size: float = Field(default=.005, gt=0)
    time_step: float | None = Field(default=None, gt=0)
    iterations: int = Field(default=300, ge=1)
    time_steps: int = Field(default=20, ge=1)
    iterations_per_step: int = Field(default=20, ge=1)
    processors: int = Field(default=2, ge=1, le=32)
    max_runtime_seconds: float = Field(default=3600, gt=0)
    @model_validator(mode='after')
    def timestep(self):
        if self.mode == 'transient' and self.time_step is None:
            raise ValueError('transient simulation requires time_step')
        return self

class ValidationPolicy(StrictModel):
    max_skewness: float = Field(default=.95, gt=0, le=1)
    min_orthogonal_quality: float = Field(default=.1, gt=0, le=1)
    aspect_ratio_warning: float = Field(default=100, gt=0)
    mass_imbalance_fraction: float = Field(default=.01, gt=0, lt=1)
    energy_imbalance_fraction: float = Field(default=.02, gt=0, lt=1)
    residual: float = Field(default=1e-4, gt=0, lt=1)
    energy_residual: float = Field(default=1e-6, gt=0, lt=1)
    temperature_tolerance: float = Field(default=.5, ge=0)
    mixing_temperature_warning: float = Field(default=1, gt=0)
    monitor_window: int = Field(default=10, ge=3)
    monitor_temperature_span: float = Field(default=.1, gt=0)
    max_velocity_factor: float = Field(default=10, gt=1)
    max_absolute_pressure: float = Field(default=1e7, gt=101325)

class SimulationSpec(StrictModel):
    geometry: Geometry
    cold: Inlet
    hot: Inlet
    material: Material = Field(default_factory=Material)
    controls: Controls = Field(default_factory=Controls)
    validation: ValidationPolicy = Field(default_factory=ValidationPolicy)
    @model_validator(mode='after')
    def temperatures(self):
        if self.hot.temperature <= self.cold.temperature:
            raise ValueError('hot temperature must exceed cold temperature')
        return self

class CheckResult(StrictModel):
    stage: str
    name: str
    status: Literal['PASS','WARNING','BLOCKER','UNVERIFIED']
    message: str
    value: float | None = None
    evidence: str | None = None

class RunRecord(StrictModel):
    status: str = 'created'
    stages: list[str] = Field(default_factory=list)
    checks: list[CheckResult] = Field(default_factory=list)
    error: str | None = None

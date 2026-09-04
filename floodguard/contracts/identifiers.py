"""Canonical identifier types used across FloodGuard-AI domains."""

from typing import NewType
from uuid import UUID

CityId = NewType("CityId", UUID)
SourceId = NewType("SourceId", UUID)
DatasetId = NewType("DatasetId", UUID)
DatasetVersionId = NewType("DatasetVersionId", UUID)
WardId = NewType("WardId", UUID)
CatchmentId = NewType("CatchmentId", UUID)
TwinId = NewType("TwinId", UUID)
DrainNodeId = NewType("DrainNodeId", UUID)
DrainEdgeId = NewType("DrainEdgeId", UUID)
ExchangeId = NewType("ExchangeId", UUID)
ExchangeBindingId = NewType("ExchangeBindingId", UUID)
RoadEdgeId = NewType("RoadEdgeId", UUID)
RainEventId = NewType("RainEventId", UUID)
ForcingPackageId = NewType("ForcingPackageId", UUID)
HydraulicStateId = NewType("HydraulicStateId", UUID)
SimulationId = NewType("SimulationId", UUID)
ForecastId = NewType("ForecastId", UUID)
ScenarioId = NewType("ScenarioId", UUID)
RouteId = NewType("RouteId", UUID)
JobId = NewType("JobId", UUID)

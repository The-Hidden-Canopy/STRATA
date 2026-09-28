"""Authoritative geodetic coordinates and local ENU engineering frames."""

from __future__ import annotations

import math
from dataclasses import dataclass


WGS84_A = 6378137.0
WGS84_E2 = 6.6943799901413165e-3


@dataclass(frozen=True, slots=True)
class Geodetic:
    latitude: float
    longitude: float
    height_m: float = 0.0
    crs: str = "EPSG:4979"


@dataclass(frozen=True, slots=True)
class ECEF:
    x: float
    y: float
    z: float


@dataclass(frozen=True, slots=True)
class ENU:
    east: float
    north: float
    up: float


def geodetic_to_ecef(value: Geodetic) -> ECEF:
    lat, lon = math.radians(value.latitude), math.radians(value.longitude)
    sin_lat, cos_lat = math.sin(lat), math.cos(lat)
    sin_lon, cos_lon = math.sin(lon), math.cos(lon)
    radius = WGS84_A / math.sqrt(1 - WGS84_E2 * sin_lat * sin_lat)
    return ECEF((radius + value.height_m) * cos_lat * cos_lon, (radius + value.height_m) * cos_lat * sin_lon, (radius * (1 - WGS84_E2) + value.height_m) * sin_lat)


def ecef_to_enu(origin: Geodetic, point: ECEF) -> ENU:
    base = geodetic_to_ecef(origin)
    dx, dy, dz = point.x - base.x, point.y - base.y, point.z - base.z
    lat, lon = math.radians(origin.latitude), math.radians(origin.longitude)
    return ENU(-math.sin(lon) * dx + math.cos(lon) * dy, -math.sin(lat) * math.cos(lon) * dx - math.sin(lat) * math.sin(lon) * dy + math.cos(lat) * dz, math.cos(lat) * math.cos(lon) * dx + math.cos(lat) * math.sin(lon) * dy + math.sin(lat) * dz)


def enu_to_ecef(origin: Geodetic, local: ENU) -> ECEF:
    base = geodetic_to_ecef(origin)
    lat, lon = math.radians(origin.latitude), math.radians(origin.longitude)
    dx = -math.sin(lon) * local.east - math.sin(lat) * math.cos(lon) * local.north + math.cos(lat) * math.cos(lon) * local.up
    dy = math.cos(lon) * local.east - math.sin(lat) * math.sin(lon) * local.north + math.cos(lat) * math.sin(lon) * local.up
    dz = math.cos(lat) * local.north + math.sin(lat) * local.up
    return ECEF(base.x + dx, base.y + dy, base.z + dz)


def transform(value: Geodetic, target_crs: str) -> Geodetic:
    """Preserve CRS intent; identity conversion is the dependency-free MVP."""
    if value.crs != target_crs:
        raise ValueError(f"CRS conversion requires PROJ adapter: {value.crs} -> {target_crs}")
    return value


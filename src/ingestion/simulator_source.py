import math
import time
import random
import threading
import queue
from dataclasses import dataclass
from typing import Tuple

from .airports import AIRPORTS


def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    R = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(a))


def _gc_point(lat1, lon1, lat2, lon2, f: float) -> Tuple[float, float]:
    φ1, λ1, φ2, λ2 = map(math.radians, [lat1, lon1, lat2, lon2])
    d = 2*math.asin(math.sqrt(
        math.sin((φ2-φ1)/2)**2 + math.cos(φ1)*math.cos(φ2)*math.sin((λ2-λ1)/2)**2
    ))
    if d < 1e-9:
        return lat1, lon1
    A = math.sin((1-f)*d) / math.sin(d)
    B = math.sin(f*d)     / math.sin(d)
    x = A*math.cos(φ1)*math.cos(λ1) + B*math.cos(φ2)*math.cos(λ2)
    y = A*math.cos(φ1)*math.sin(λ1) + B*math.cos(φ2)*math.sin(λ2)
    z = A*math.sin(φ1)               + B*math.sin(φ2)
    return (
        math.degrees(math.atan2(z, math.sqrt(x**2 + y**2))),
        math.degrees(math.atan2(y, x)),
    )


def _bearing(lat1, lon1, lat2, lon2) -> float:
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δλ = math.radians(lon2 - lon1)
    x = math.sin(Δλ) * math.cos(φ2)
    y = math.cos(φ1)*math.sin(φ2) - math.sin(φ1)*math.cos(φ2)*math.cos(Δλ)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def _altitude_m(f: float, cruise=10_668.0) -> float:
    if f < 0.12:  return cruise * (f / 0.12)
    if f > 0.88:  return cruise * (1 - (f - 0.88) / 0.12)
    return cruise


def _speed_ms(f: float, cruise=245.0) -> float:
    if f < 0.05 or f > 0.95: return cruise * 0.35
    if f < 0.12: return cruise * (0.35 + 0.65*(f-0.05)/0.07)
    if f > 0.88: return cruise * (0.35 + 0.65*(0.95-f)/0.07)
    return cruise


_AIRLINE_PREFIXES = [
    "UAL","DAL","BAW","AFR","DLH","UAE","SIA","QFA","AAL","THY",
    "ANA","JAL","KAL","CES","CSN","QTR","ETH","TAM","KLM","AZU",
]


@dataclass
class _SimFlight:
    icao24: str
    callsign: str
    origin_icao: str
    dest_icao: str
    olat: float; olon: float
    dlat: float; dlon: float
    dist_m: float
    duration_s: float
    started_at: float
    speed_factor: float

    def _fraction(self) -> float:
        elapsed = (time.time() - self.started_at) * self.speed_factor
        return min(1.0, elapsed / self.duration_s)

    def is_done(self) -> bool:
        return self._fraction() >= 1.0

    def state(self) -> dict:
        f = self._fraction()
        lat, lon = _gc_point(self.olat, self.olon, self.dlat, self.dlon, f)
        return {
            "icao24":        self.icao24,
            "callsign":      self.callsign,
            "latitude":      round(lat, 5),
            "longitude":     round(lon, 5),
            "altitude":      round(_altitude_m(f), 0),
            "velocity":      round(_speed_ms(f), 1),
            "true_track":    round(_bearing(self.olat, self.olon, self.dlat, self.dlon), 1),
            "vertical_rate": 0.0,
            "on_ground":     False,
            "origin_icao":   self.origin_icao,
            "dest_icao":     self.dest_icao,
            "progress":      round(f * 100, 1),
            "last_contact":  int(time.time()),
        }


class SimulatorSource:
    def __init__(self,
                 out_queue: queue.Queue,
                 num_flights: int = 200,
                 speed_factor: float = 60.0,
                 poll_interval: float = 2.0):
        self.out_queue     = out_queue
        self.num_flights   = num_flights
        self.speed_factor  = speed_factor
        self.poll_interval = poll_interval
        self._flights: dict[str, _SimFlight] = {}
        self._lock  = threading.Lock()
        self._stop  = threading.Event()

    def _spawn(self) -> _SimFlight:
        origin, dest = random.sample(AIRPORTS, 2)
        dist = _haversine_m(origin[2], origin[3], dest[2], dest[3])
        duration_s = dist / 245.0
        return _SimFlight(
            icao24       = format(random.randint(0, 0xFFFFFF), '06x'),
            callsign     = random.choice(_AIRLINE_PREFIXES) + str(random.randint(1, 9999)).zfill(4),
            origin_icao  = origin[0],
            dest_icao    = dest[0],
            olat=origin[2], olon=origin[3],
            dlat=dest[2],   dlon=dest[3],
            dist_m       = dist,
            duration_s   = duration_s,
            started_at   = time.time() - random.uniform(0, duration_s / self.speed_factor),
            speed_factor = self.speed_factor,
        )

    def _refill(self):
        with self._lock:
            for k in [k for k, v in self._flights.items() if v.is_done()]:
                del self._flights[k]
            while len(self._flights) < self.num_flights:
                f = self._spawn()
                self._flights[f.icao24] = f

    def _tick(self):
        self._refill()
        with self._lock:
            states = [f.state() for f in self._flights.values()]
        try:
            self.out_queue.put_nowait({"states": states, "timestamp": time.time()})
        except queue.Full:
            pass

    def run(self):
        while not self._stop.is_set():
            self._tick()
            time.sleep(self.poll_interval)

    def stop(self):
        self._stop.set()

from __future__ import annotations

import math
import time
from datetime import datetime, timedelta, timezone
from typing import Sequence

from .generator import TelemetryGenerator
from .models import AssetConfig
from .sinks import BaseSink
from .validators import validate_event


class PLCSimulator:
    def __init__(
        self,
        assets: Sequence[AssetConfig],
        generator: TelemetryGenerator,
        sink: BaseSink,
        interval_seconds: float = 5.0,
        duration_seconds: float | None = None,
        realtime: bool = True,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be greater than 0")
        if not assets:
            raise ValueError("at least one asset is required")

        self.assets = list(assets)
        self.generator = generator
        self.sink = sink
        self.interval_seconds = interval_seconds
        self.duration_seconds = duration_seconds
        self.realtime = realtime

    def run(self) -> int:
        emitted = 0
        start_time = datetime.now(timezone.utc)

        if self.duration_seconds is None:
            cycle = 0
            while True:
                emitted += self._emit_cycle(start_time + timedelta(seconds=cycle * self.interval_seconds))
                cycle += 1
                if self.realtime:
                    time.sleep(self.interval_seconds)

        total_cycles = max(1, math.ceil(self.duration_seconds / self.interval_seconds))
        for cycle in range(total_cycles):
            emitted += self._emit_cycle(start_time + timedelta(seconds=cycle * self.interval_seconds))
            if self.realtime and cycle < total_cycles - 1:
                time.sleep(self.interval_seconds)

        return emitted

    def _emit_cycle(self, event_time: datetime) -> int:
        emitted = 0
        for asset in self.assets:
            event = self.generator.generate_event(asset, event_time=event_time)
            payload = event.to_dict()
            validate_event(payload)
            self.sink.write(event)
            emitted += 1
        return emitted

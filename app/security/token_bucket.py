"""Single-process, per-user request token bucket. Clock is monotonic; not LLM token accounting."""
import math
import threading
import time

class TokenBucket:
    def __init__(self, capacity=10, refill_per_sec=0.5, clock=time.monotonic):
        if capacity < 1 or refill_per_sec <= 0:
            raise ValueError("capacity >= 1 and refill_per_sec > 0 required")
        self.capacity, self.rate, self.clock = capacity, refill_per_sec, clock
        self.state, self.lock = {}, threading.Lock()

    def consume(self, user_id):
        with self.lock:
            now = self.clock()
            tokens, then = self.state.get(user_id, (self.capacity, now))
            tokens = min(self.capacity, tokens + max(0, now - then) * self.rate)
            ok = tokens >= 1
            self.state[user_id] = (tokens - 1 if ok else tokens, now)
            return ok, 0 if ok else max(1, math.ceil((1 - tokens) / self.rate))

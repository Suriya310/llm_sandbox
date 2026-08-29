import time
from typing import Callable, Awaitable
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import config

class RateLimiterMiddleware(BaseHTTPMiddleware):
    """
    Simple sliding window rate limiter middleware.
    """

    def __init__(self, app, requests_per_window: int = None, window_seconds: int = None):
        super().__init__(app)
        self.requests_per_window = requests_per_window if requests_per_window is not None else config.settings.RATE_LIMIT_REQUESTS
        self.window_seconds = window_seconds if window_seconds is not None else config.settings.RATE_LIMIT_WINDOW
        # Structure: {client_ip: [timestamp1, timestamp2, ...]}
        self.request_logs = {}

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        client_ip = self._get_client_ip(request)
        now = time.time()
        window_start = now - self.window_seconds

        # Initialize or clean the log for this IP
        if client_ip not in self.request_logs:
            self.request_logs[client_ip] = []
        # Remove timestamps older than the window
        self.request_logs[client_ip] = [t for t in self.request_logs[client_ip] if t > window_start]

        # Check if the rate limit has been exceeded
        if len(self.request_logs[client_ip]) >= self.requests_per_window:
            return JSONResponse(
                status_code=429,
                content={"detail": f"Rate limit exceeded. Maximum {self.requests_per_window} requests per {self.window_seconds} seconds."}
            )

        # Add the current request timestamp
        self.request_logs[client_ip].append(now)

        # Proceed with the request
        response = await call_next(request)
        return response

    def _get_client_ip(self, request: Request) -> str:
        """
        Extract client IP, considering common proxy headers.
        Note: In a production setup behind a proxy, you should configure trusted proxies.
        For this assignment, we use a simple approach.
        """
        # X-Forwarded-For can contain multiple IPs; we take the first one (the client)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # The first IP in the list is the client
            ip = forwarded.split(",")[0].strip()
        else:
            # Fallback to X-Real-IP or the direct client host
            ip = request.headers.get("X-Real-IP", request.client.host if request.client else "unknown")
        return ip

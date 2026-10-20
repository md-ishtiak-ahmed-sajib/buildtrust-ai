"""Bound ingestion before multipart parsing; log metadata only, never bodies/secrets."""

from collections import deque
import asyncio
import json
import logging
import time
import uuid
from functools import wraps
from .bounded_json import check_shape

log = logging.getLogger("buildtrust.operations")
if not log.handlers:
    log.addHandler(logging.StreamHandler())
log.setLevel(logging.INFO)
log.propagate = False


def timed(event):
    """Log fixed operation metadata only; never stringify arguments or errors."""
    def decorate(function):
        @wraps(function)
        def run(*args, **kwargs):
            started, outcome = time.monotonic(), "FAILED"
            try:
                result = function(*args, **kwargs)
                outcome = "COMPLETE"
                return result
            finally:
                log.info(json.dumps({"event": event, "outcome": outcome,
                                     "duration_ms": round((time.monotonic() - started) * 1000)}))
        return run
    return decorate


class RequestBoundary:
    def __init__(self, app, max_body, body_timeout=15):
        self.app, self.max_body, self.body_timeout = app, max_body, body_timeout

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request_id, started = uuid.uuid4().hex, time.monotonic()
        scope["request_id"] = request_id
        headers = dict(scope.get("headers", []))
        async def reject(status, code, message):
            payload = json.dumps({"error": {"code": code, "message": message,
                                            "request_id": request_id}}).encode()
            await send({"type": "http.response.start", "status": status,
                        "headers": [(b"content-type", b"application/json"),
                                    (b"cache-control", b"no-store"),
                                    (b"x-content-type-options", b"nosniff"),
                                    (b"content-security-policy", b"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"),
                                    (b"x-request-id", request_id.encode())]})
            await send({"type": "http.response.body", "body": payload})
            log.info(json.dumps({"event": "http_request", "request_id": request_id,
                                 "method": scope["method"], "path": scope["path"],
                                 "status": status, "duration_ms": round((time.monotonic()-started)*1000)}))
        try:
            length = int(headers.get(b"content-length", b"0"))
        except ValueError:
            length = self.max_body + 1
        chunks, size = deque(), 0
        # Buffer at most the configured bound, including requests with no
        # Content-Length. Starlette has not parsed multipart at this boundary.
        if length <= self.max_body and scope["method"] in ("POST", "PUT", "PATCH"):
            while True:
                try:
                    remaining = self.body_timeout - (time.monotonic() - started)
                    message = await asyncio.wait_for(receive(), timeout=max(0, remaining))
                except TimeoutError:
                    return await reject(408, "BODY_TIMEOUT", "Request body was not received within the processing limit.")
                if message["type"] == "http.disconnect":
                    return
                size += len(message.get("body", b""))
                if size > self.max_body:
                    break
                chunks.append(message)
                if not message.get("more_body", False):
                    break
        if length > self.max_body or size > self.max_body:
            return await reject(413, "REQUEST_TOO_LARGE", "Request exceeds the bounded upload envelope.")
        if b"application/json" in headers.get(b"content-type", b"").lower():
            try:
                check_shape(b"".join(message.get("body", b"") for message in chunks))
            except ValueError as exc:
                return await reject(422, "JSON_LIMIT", str(exc))

        async def bounded_receive():
            return chunks.popleft() if chunks else await receive()

        status = 500
        response_started = False

        async def tagged_send(message):
            nonlocal status, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status = message["status"]
                message.setdefault("headers", []).append(
                    (b"x-request-id", request_id.encode())
                )
            await send(message)

        try:
            await self.app(scope, bounded_receive, tagged_send)
        except Exception:
            # Handle failures inside the boundary so the ASGI server cannot log
            # an exception containing credentials, request bodies or URLs.
            log.error(json.dumps({"event": "request_failed", "request_id": request_id}))
            if not response_started:
                status = 500
                return await reject(500, "INTERNAL_ERROR", "The operation could not be completed. Use the request ID when reporting it.")
            await send({"type": "http.response.body", "body": b"", "more_body": False})
        finally:
            log.info(
                json.dumps(
                    {
                        "event": "http_request",
                        "request_id": request_id,
                        "method": scope["method"],
                        "path": scope["path"],
                        "status": status,
                        "duration_ms": round((time.monotonic() - started) * 1000),
                        "body_bytes": size,
                    }
                )
            )

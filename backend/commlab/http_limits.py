"""Bound request bytes before parsing multipart bodies or JSON."""
from fastapi.responses import JSONResponse


class BodyLimit:
    def __init__(self, app, limit=2_100_000):
        self.app, self.limit = app, limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in ["POST", "PUT", "PATCH"]:
            return await self.app(scope, receive, send)
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > self.limit:
                response = JSONResponse({"code": "upload_size", "message": "Request exceeds 2.1 MB.", "correlation_id": "body-limit"}, status_code=413)
                return await response(scope, receive, send)
            if not message.get("more_body", False):
                break
        sent = False
        async def replay():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()
        await self.app(scope, replay, send)

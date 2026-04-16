"""Patch FastAPI's OpenAPI route to expose the actual exception."""
import traceback
import sys
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
import fastapi.applications as _apps

_original_setup = _apps.FastAPI.setup

def _patched_setup(self):
    _original_setup(self)
    # Replace the openapi route handler
    for route in self.routes:
        if hasattr(route, 'path') and route.path == self.openapi_url:
            _orig_endpoint = route.endpoint
            async def _safe_endpoint(*args, _orig=_orig_endpoint, **kwargs):
                try:
                    return await _orig(*args, **kwargs)
                except Exception as exc:
                    print("OPENAPI ROUTE ERROR:", file=sys.stderr)
                    traceback.print_exc(file=sys.stderr)
                    return PlainTextResponse(traceback.format_exc(), status_code=500)
            route.endpoint = _safe_endpoint
            break

_apps.FastAPI.setup = _patched_setup

from app.main import app  # noqa
import uvicorn
uvicorn.run(app, host="0.0.0.0", port=8000)

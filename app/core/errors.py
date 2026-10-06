from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorBody(BaseModel):
    error: str
    message: str


_ERROR_TEXT = {
    400: "The request or file was not acceptable.",
    401: "Not signed in, or the credentials were wrong.",
    403: "Signed in, but the role is too low for this action.",
    404: "Not found, or not visible to this user.",
    409: "Conflicts with the current state.",
    413: "The upload is too large.",
    503: "Processing is temporarily unavailable.",
}


def errors(*codes: int) -> dict:
    """Describe error responses in the generated docs."""
    return {code: {"model": ErrorBody, "description": _ERROR_TEXT[code]} for code in codes}


class ApiError(HTTPException):
    """An error that always renders as {"error": code, "message": text}."""

    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(status_code=status_code, detail={"error": code, "message": message})


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            body = exc.detail
        else:
            body = {"error": "http_error", "message": str(exc.detail)}
        return JSONResponse(body, status_code=exc.status_code, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        first = exc.errors()[0]
        where = ".".join(str(p) for p in first["loc"] if p != "body")
        return JSONResponse(
            {"error": "validation_error", "message": f"{where}: {first['msg']}"},
            status_code=422,
        )

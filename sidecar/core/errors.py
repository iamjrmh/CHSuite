"""Structured API errors shared across sidecar handlers."""

from __future__ import annotations


class ApiError(Exception):
    """An error that maps to a clean HTTP response.

    ``status`` is the HTTP status code, ``code`` a short machine string the
    frontend can switch on, and ``data`` optional extra context.
    """

    def __init__(self, message: str, *, code: str = "error", status: int = 400, data=None):
        super().__init__(message)
        self.code = code
        self.status = status
        self.data = data


class MissingDependency(ApiError):
    """Raised when an optional library (UnityPy, Pillow, requests) is absent."""

    def __init__(self, package: str, feature: str):
        super().__init__(
            f"The '{package}' Python package is required for {feature} but is not installed.",
            code="missing_dependency",
            status=503,
            data={"package": package, "feature": feature},
        )

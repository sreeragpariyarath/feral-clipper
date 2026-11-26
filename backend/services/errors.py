"""Errors the services raise. The API maps each one to an HTTP status, so routes never catch them."""


class ServiceError(Exception):
    status_code = 400


class InvalidInput(ServiceError):
    status_code = 400


class NotFound(ServiceError):
    status_code = 404


class Conflict(ServiceError):
    status_code = 409

class BillAvenueClientError(Exception):
    """Base integration error for BillAvenue API failures."""


class BillAvenueValidationError(BillAvenueClientError):
    """Request validation error before or after provider call."""


class BillAvenueTransportError(BillAvenueClientError):
    """Network/timeout/TLS related provider transport error."""


class BillAvenueAuthError(BillAvenueClientError):
    """Authentication/envelope failure with BillAvenue."""


class BillAvenueDuplicateRequestError(BillAvenueClientError):
    """Duplicate request identifier rejection."""


ERROR_CODE_MAP = {
    'PP001': BillAvenueAuthError,
    'PP002': BillAvenueValidationError,
    'PP003': BillAvenueDuplicateRequestError,
}


def exception_for_code(code: str):
    return ERROR_CODE_MAP.get(str(code or '').strip().upper(), BillAvenueClientError)

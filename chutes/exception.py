class InvalidPath(ValueError):
    ...


class DuplicatePath(ValueError):
    ...


class AuthenticationRequired(RuntimeError):
    ...


class NotConfigured(RuntimeError):
    ...


class StillProvisioning(RuntimeError):
    ...

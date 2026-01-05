class ConnectionRetry(RuntimeError):
    def __init__(
        self,
        engine: str,
        message: str,
        *,
        attempts: int | None = None,
        last_exc: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.engine = engine
        self.attempts = attempts
        self.last_exc = last_exc

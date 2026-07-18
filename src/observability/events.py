import structlog


def configure_logging(log_level: str = "INFO") -> None:
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(__import__("logging"), log_level, 20)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )


def get_logger(name: str = "agent") -> structlog.BoundLogger:
    # Bind the logger name into the event dict. We do NOT use
    # structlog.stdlib.add_logger_name here because PrintLogger (our factory)
    # has no `.name` attribute, which would raise on every log call once
    # configure_logging() has run.
    return structlog.get_logger().bind(logger=name)

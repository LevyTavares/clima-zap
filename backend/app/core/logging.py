import logging
import sys


def setup_logging() -> logging.Logger:
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )

    app_logger = logging.getLogger("clima_zap")
    app_logger.info("Sistema de logs estruturados inicializado com sucesso.")
    return app_logger


logger = setup_logging()
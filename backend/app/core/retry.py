import asyncio
from functools import wraps
from typing import Any, Callable, Type

from app.core.logging import logger


def async_retry(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple[Type[Exception], ...] = (Exception,),
) -> Callable:
    """
    Decorador assíncrono para retentar funções em caso de exceções temporárias.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            current_delay = delay
            for attempt in range(1, max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as exc:
                    if attempt == max_retries:
                        logger.error(
                            f"Falha definitiva em '{func.__name__}' após {max_retries} tentativas. Erro: {exc}"
                        )
                        raise exc

                    logger.warning(
                        f"Tentativa {attempt}/{max_retries} de '{func.__name__}' falhou: {exc}. "
                        f"Tentando novamente em {current_delay:.1f}s..."
                    )
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff_factor

        return wrapper

    return decorator
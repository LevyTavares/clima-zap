import pytest
from app.core.retry import async_retry


@pytest.mark.asyncio
async def test_async_retry_recovers_on_second_attempt():
    attempts = 0

    @async_retry(max_retries=3, delay=0.01, backoff_factor=1.0)
    async def mock_api_call():
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise ConnectionError("Instabilidade temporária de rede")
        return "ok"

    result = await mock_api_call()
    assert result == "ok"
    assert attempts == 2


@pytest.mark.asyncio
async def test_async_retry_raises_exception_after_max_retries():
    attempts = 0

    @async_retry(max_retries=3, delay=0.01, backoff_factor=1.0)
    async def failing_api_call():
        nonlocal attempts
        attempts += 1
        raise TimeoutError("Serviço indisponível")

    with pytest.raises(TimeoutError):
        await failing_api_call()

    assert attempts == 3
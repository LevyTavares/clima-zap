from fastapi import APIRouter, status

router = APIRouter(prefix="/api/v1/forecast", tags=["Forecast"])

@router.get("/preview", status_code=status.HTTP_200_OK)
async def get_forecast_preview():
    """
    Endpoint de visualização do relatório de clima para teste rápido de layout direto pelo Swagger UI.
    """
    return {
        "cidade": "Juazeiro do Norte",
        "temperatura": "28°C",
        "condicao": "Chuva forte"
    }
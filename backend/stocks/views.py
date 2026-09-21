from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .services.market_data import InvalidTicker, NoMarketData
from .services.stock_service import StockService


@require_GET
def stock_summary(request, ticker):
    try:
        result = StockService(ticker).summary()
    except InvalidTicker:
        return JsonResponse({"error": "Invalid ticker symbol."}, status=400)
    except NoMarketData:
        return JsonResponse({"error": "No market data available."}, status=404)
    except RuntimeError:
        return JsonResponse({"error": "Market data provider failed."}, status=502)
    return JsonResponse(result, json_dumps_params={"allow_nan": False})

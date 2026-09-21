from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .services.market_data import InvalidTicker, NoMarketData, search_symbols
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


@require_GET
def stock_history(request, ticker):
    try:
        result = StockService(ticker).history(request.GET.get("range", "3m"))
    except InvalidTicker:
        return JsonResponse({"error": "Invalid ticker symbol."}, status=400)
    except NoMarketData:
        return JsonResponse({"error": "No market data available."}, status=404)
    except ValueError:
        return JsonResponse({"error": "Invalid history range."}, status=400)
    except RuntimeError:
        return JsonResponse({"error": "Market data provider failed."}, status=502)
    return JsonResponse(result, json_dumps_params={"allow_nan": False})


@require_GET
def stock_compare(request):
    requested = request.GET.get("symbols", "").split(",")
    if not 2 <= len(requested) <= 3:
        return JsonResponse({"error": "Provide 2 or 3 unique ticker symbols."}, status=400)
    try:
        # Validate the entire list before any summary can access the provider.
        services = [StockService(symbol) for symbol in requested]
        symbols = [service.symbol for service in services]
        if len(set(symbols)) != len(symbols):
            return JsonResponse({"error": "Provide 2 or 3 unique ticker symbols."}, status=400)
        results = [service.summary() for service in services]
    except InvalidTicker:
        return JsonResponse({"error": "Invalid ticker symbol."}, status=400)
    except NoMarketData:
        return JsonResponse({"error": "No market data available."}, status=404)
    except RuntimeError:
        return JsonResponse({"error": "Market data provider failed."}, status=502)
    return JsonResponse(
        {"symbols": symbols, "results": results}, json_dumps_params={"allow_nan": False}
    )


@require_GET
def stock_search(request):
    try:
        results = search_symbols(request.GET.get("q", ""))
    except ValueError:
        return JsonResponse({"error": "Invalid search query."}, status=400)
    except RuntimeError:
        return JsonResponse({"error": "Market search is unavailable."}, status=502)
    return JsonResponse({"results": results})

import aiohttp
from config import LAVATOP_API_KEY
import uuid

async def create_payment_link(offer_id: str, email: str, user_id: int) -> dict:
    """
    Создает ссылку на оплату через Lava.top API v3.
    """
    payload = {
        "email": email,
        "offerId": offer_id,
        "currency": "RUB",
        # Здесь мы не указываем явно провайдера, будет использован по умолчанию для RUB (SMART_GLOCAL)
        # Также можно передать clientUtm для отслеживания user_id, если необходимо
    }
    
    headers = {
        "X-Api-Key": LAVATOP_API_KEY,
        "Content-Type": "application/json"
    }
    
    api_url = "https://gate.lava.top/api/v3/invoice"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, json=payload, headers=headers) as resp:
                if resp.status == 201:
                    data = await resp.json()
                    # data имеет схему InvoicePaymentParamsResponse, возвращаем нужные поля
                    return {
                        "url": data.get("paymentUrl"),
                        "order_id": data.get("id")
                    }
                else:
                    error_text = await resp.text()
                    print(f"Lava.top API Error: {resp.status} - {error_text}")
                    return None
    except Exception as e:
        print(f"Request exception: {e}")
        return None

async def check_payment_status(order_id: str) -> str:
    """
    Проверяет статус контракта (инвойса) по его ID.
    """
    headers = {
        "X-Api-Key": LAVATOP_API_KEY
    }
    api_url = f"https://gate.lava.top/api/v2/invoices/{order_id}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("status")
                else:
                    return None
    except Exception as e:
        print(f"Check payment exception: {e}")
        return None


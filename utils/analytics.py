from typing import Dict


def calculate_cpm(avg_views: int) -> float:
    """CPM за 1000 просмотров"""
    if avg_views < 100:
        return 0.5
    elif avg_views < 500:
        return 1.0
    elif avg_views < 1000:
        return 1.5
    elif avg_views < 5000:
        return 2.0
    elif avg_views < 10000:
        return 2.5
    elif avg_views < 50000:
        return 3.0
    else:
        return 4.0


def calculate_err(subscribers: int, avg_views: int) -> float:
    """Engagement Rate"""
    if subscribers == 0:
        return 0
    return (avg_views / subscribers) * 100


def calculate_recommended_price(subscribers: int, avg_views: int) -> Dict[str, float]:
    """Рекомендуемая цена за 1 день"""
    if subscribers == 0 or avg_views == 0:
        return {"post": 0.0, "pin": 0.0, "cpm": 0.0, "err": 0.0}
    
    cpm = calculate_cpm(avg_views)
    err = calculate_err(subscribers, avg_views)
    
    if err > 50:
        cpm *= 0.7
    elif err > 30:
        cpm *= 1.3
    elif err > 15:
        cpm *= 1.1
    elif err < 5:
        cpm *= 0.8
    
    post_price = round((avg_views / 1000) * cpm, 2)
    pin_price = round(post_price * 2, 2)
    
    post_price = max(post_price, 0.5)
    pin_price = max(pin_price, 1.0)
    
    return {
        "post": post_price,
        "pin": pin_price,
        "cpm": round(cpm, 2),
        "err": round(err, 1)
    }


def calculate_total_price(price_per_day: float, days: int) -> float:
    """Общая стоимость за N дней"""
    return round(price_per_day * days, 2)

import random
import time


def unique_mobile(prefix: str = "139") -> str:
    suffix = f"{int(time.time()) % 100000:05d}{random.randint(100, 999)}"
    return f"{prefix}{suffix}"


def default_password() -> str:
    return "Test@123456"


def default_address_payload() -> dict:
    return {
        "receiverName": "Auto Tester",
        "receiverPhone": "13900001111",
        "province": "Guangdong",
        "city": "Shenzhen",
        "district": "Nanshan",
        "detailAddress": "Science Park 1st Road",
        "isDefault": True,
    }

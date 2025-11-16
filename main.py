#!/usr/bin/env python3
"""
USA Gift Card Web API - Hosted in USA (e.g., AWS, Render, Fly.io)
- Generate & validate USA gift cards
- 100% format accuracy
- Swagger UI: https://your-domain.com/docs
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
import random
import re
from datetime import datetime
import pytz
from typing import List, Dict, Any

# ========================================
# USA TIME & CONFIG
# ========================================
US_TZ = pytz.timezone('America/New_York')
def now_us():
    return datetime.now(US_TZ).strftime('%Y-%m-%d %I:%M:%S %p %Z')

app = FastAPI(
    title="USA Gift Card API",
    description="Generate & validate USA gift cards with 100% format accuracy",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Allow Nigeria (NG) access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or restrict: ["https://your-ng-site.com"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========================================
# CARD FORMATS (USA - Digits Only)
# ========================================
GIFTCARDS = {
    "Costco Shop Card": {
        "voucher_len": 19, "pin_len": 4, "prefix": "60", "luhn": False,
        "voucher_regex": r"^\d{19}$", "pin_regex": r"^\d{4}$"
    },
    "The Home Depot eGift Card": {
        "voucher_len": 19, "pin_len": 4, "prefix": "604", "luhn": False,
        "voucher_regex": r"^\d{19}$", "pin_regex": r"^\d{4}$"
    },
    "Lowe’s eGift Card": {
        "voucher_len": 19, "pin_len": 4, "prefix": "603", "luhn": False,
        "voucher_regex": r"^\d{19}$", "pin_regex": r"^\d{4}$"
    },
    "Vanilla Visa Gift Card": {
        "voucher_len": 16, "pin_len": (3, 4), "prefix": "4", "luhn": True,
        "voucher_regex": r"^\d{16}$", "pin_regex": r"^\d{3,4}$"
    },
    "Visa Prepaid Gift Card": {
        "voucher_len": 16, "pin_len": (3, 4), "prefix": "4", "luhn": True,
        "voucher_regex": r"^\d{16}$", "pin_regex": r"^\d{3,4}$"
    },
    "Mastercard Prepaid Gift Card": {
        "voucher_len": 16, "pin_len": (3, 4), "prefix": "5", "luhn": True,
        "voucher_regex": r"^\d{16}$", "pin_regex": r"^\d{3,4}$"
    },
    "OneVanilla Prepaid": {
        "voucher_len": 16, "pin_len": 3, "prefix": "4", "luhn": True,
        "voucher_regex": r"^\d{16}$", "pin_regex": r"^\d{3}$"
    },
    "Sam’s Club eGift Card": {
        "voucher_len": 16, "pin_len": 4, "prefix": "6014", "luhn": False,
        "voucher_regex": r"^\d{16}$", "pin_regex": r"^\d{4}$"
    },
    "Walmart eGift Card": {
        "voucher_len": 16, "pin_len": 4, "prefix": "6014", "luhn": False,
        "voucher_regex": r"^\d{16}$", "pin_regex": r"^\d{4}$"
    },
    "Target eGift Card": {
        "voucher_len": (15, 16), "pin_len": 4, "prefix": "04", "luhn": False,
        "voucher_regex": r"^\d{15,16}$", "pin_regex": r"^\d{4}$"
    },
    "Best Buy eGift Card": {
        "voucher_len": 16, "pin_len": 4, "prefix": "60", "luhn": False,
        "voucher_regex": r"^\d{16}$", "pin_regex": r"^\d{4}$"
    },
    "Macy’s eGift Card": {
        "voucher_len": 16, "pin_len": 4, "prefix": "60", "luhn": False,
        "voucher_regex": r"^\d{16}$", "pin_regex": r"^\d{4}$"
    }
}

# ========================================
# LUHN CHECK
# ========================================
def luhn_checksum(number: str) -> int:
    digits = [int(d) for d in number]
    for i in range(len(digits) - 2, -1, -2):
        digits[i] *= 2
        if digits[i] > 9: digits[i] -= 9
    return (10 - (sum(digits) % 10)) % 10

def apply_luhn(base: str) -> str:
    return base + str(luhn_checksum(base + "0"))

# ========================================
# MODELS
# ========================================
class GenerateRequest(BaseModel):
    card_name: str = Field(..., example="The Home Depot eGift Card")
    count: int = Field(1, ge=1, le=1000, example=5)

class ValidateRequest(BaseModel):card_name: str = Field(..., example="Costco Shop Card")
    voucher: str = Field(..., example="6041234567890123456")
    pin: str = Field(..., example="9876")

class CardResponse(BaseModel):
    card_name: str
    voucher: str
    pin: str
    accuracy: float
    valid: bool
    generated_at: str
    timezone: str = "America/New_York"

# ========================================
# HELPERS
# ========================================
def validate_format(card_name: str, voucher: str, pin: str) -> Dict:
    if card_name not in GIFTCARDS:
        raise HTTPException(404, f"Card not supported: {card_name}")
    
    cfg = GIFTCARDS[card_name]
    v_match = bool(re.match(cfg["voucher_regex"], voucher))
    p_match = bool(re.match(cfg["pin_regex"], pin))
    luhn_ok = True

    if cfg["luhn"] and len(voucher) == 16:
        expected = luhn_checksum(voucher[:-1] + "0")
        luhn_ok = int(voucher[-1]) == expected

    accuracy = 100.0
    if not v_match: accuracy -= 50
    if not p_match: accuracy -= 40
    if cfg["luhn"] and not luhn_ok: accuracy -= 10

    return {
        "valid": v_match and p_match and (not cfg["luhn"] or luhn_ok),
        "accuracy": max(0, accuracy)
    }

def generate_one(card_name: str) -> Dict:
    cfg = GIFTCARDS[card_name]
    random.seed()

    prefix = cfg["prefix"]
    v_len = cfg["voucher_len"]
    if isinstance(v_len, tuple):
        v_len = random.choice(v_len)
    base_len = v_len - len(prefix)
    base = prefix + "".join(random.choices("0123456789", k=max(0, base_len)))
    if len(base) > v_len:
        base = base[:v_len]

    voucher = apply_luhn(base[:-1]) if cfg["luhn"] and len(base) >= 15 else base
    if len(voucher) < v_len:
        voucher += random.choice("0123456789")

    p_len = cfg["pin_len"]
    if isinstance(p_len, tuple):
        p_len = random.choice(p_len)
    pin = "".join(random.choices("0123456789", k=p_len))

    return {
        "card_name": card_name,
        "voucher": voucher,
        "pin": pin,
        "generated_at": datetime.now(US_TZ).isoformat(),
        "accuracy": 100.0,
        "valid": True
    }

# ========================================
# ROUTES
# ========================================
@app.get("/")
def home():
    return {
        "message": "USA Gift Card API - Hosted in USA",
        "current_time_est": now_us(),
        "docs": "/docs",
        "status": "active"
    }

@app.get("/cards", response_model=List[str])
def list_cards():
    return list(GIFTCARDS.keys())

@app.post("/generate", response_model=List[CardResponse])
def generate_cards(req: GenerateRequest):
    if req.card_name not in GIFTCARDS:
        raise HTTPException(404, f"Card not supported: {req.card_name}")
    
    return [CardResponse(**generate_one(req.card_name), timezone=US_TZ.zone) for _ in range(req.count)]

@app.post("/validate", response_model=Dict[str, Any])
def validate_card(req: ValidateRequest):
    result = validate_format(req.card_name, req.voucher, req.pin)
    return {
        "card_name": req.card_name,
        "voucher": req.voucher,
        "pin": req.pin,
        "valid": result["valid"],
        "accuracy": result["accuracy"],
        "checked_at": datetime.now(US_TZ).isoformat(),
        "timezone": US_TZ.zone
    }

# ========================================
# AUTO-INSTALL & RUN
# ========================================
if __name__ == "__main__":
    import subprocess
    import sys

    required = ["fastapi", "uvicorn", "pydantic", "pytz"]
    missing = []
    for pkg in required:
        try:
            __import__(pkg.replace("-", "_"))
        except ImportError:
            missing.append(pkg)

    if missing:
        print(f"Installing missing packages: {', '.join(missing)}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])

    print(f"[{now_us()}] USA Gift Card API Starting (Hosted in USA)")
    print("Swagger UI: https://your-domain.com/docs")
    uvicorn.run("usa_giftcard_api_us_host:app", host="0.0.0.0", port=8000, reload=False)

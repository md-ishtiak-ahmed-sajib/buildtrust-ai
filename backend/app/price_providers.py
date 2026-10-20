"""Authorized API adapters. No arbitrary URL fetching or fabricated live offers."""

import asyncio
from decimal import Decimal
import ipaddress
import json
import re
from urllib.parse import urlsplit
import httpx
import logging

# HTTPX INFO messages include complete query URLs. Paid search credentials must
# never enter those diagnostic messages, even if a host enables root INFO logs.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

LIMITERS = {}


def safe_url(url):
    if not url:
        return None
    parsed = urlsplit(str(url))
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
    ):
        raise ValueError("Source URL must be a public HTTPS link without credentials")
    host = parsed.hostname.lower()
    if (
        host in ("localhost", "localhost.localdomain")
        or host.endswith((".local", ".internal"))
        or "." not in host
    ):
        raise ValueError("Private source URL is not allowed")
    try:
        if not ipaddress.ip_address(host).is_global:
            raise ValueError("Private source URL is not allowed")
    except ValueError as exc:
        if "Private" in str(exc):
            raise
    return str(url)


async def api_json(method, url, settings, retry_safe=True, **kwargs):
    # All callers supply compile-time API origins, never user URLs.
    parsed = urlsplit(url)
    origin = parsed.hostname
    if (parsed.scheme != 'https' or parsed.port not in (None,443) or parsed.username or parsed.password
            or parsed.fragment or origin not in ("serpapi.com", "api.dataforseo.com", "api.frankfurter.dev")):
        raise ValueError("Unapproved provider origin")
    if origin in ("serpapi.com", "api.dataforseo.com"):
        from .admission import paid_ready
        if not paid_ready(settings, "serpapi" if origin == "serpapi.com" else "dataforseo"):
            raise ValueError("Paid providers are disabled or have no bounded budget")
    limiter = LIMITERS.setdefault(
        (id(asyncio.get_running_loop()), origin), asyncio.Semaphore(2)
    )
    async with limiter:
        async with httpx.AsyncClient(
            trust_env=False,
            timeout=httpx.Timeout(settings.price_timeout_seconds, connect=3),
            follow_redirects=False,
        ) as client:
            for attempt in range(2 if method == "GET" and retry_safe else 1):
                try:
                    async with client.stream(method, url, **kwargs) as response:
                        response.raise_for_status()
                        body = bytearray()
                        async for chunk in response.aiter_bytes():
                            body.extend(chunk)
                            if len(body) > 2 * 1024 * 1024:
                                raise ValueError("Provider response exceeds 2 MB")
                        return json.loads(body, parse_float=Decimal)
                except (httpx.TimeoutException, httpx.NetworkError):
                    if attempt or method != "GET" or not retry_safe:
                        raise
                    await asyncio.sleep(0.2)


def product_spec(title):
    spec = {}
    grade = re.search(
        r"\b(B500[ABC]|B420[ABC]|CEM\s*[IVX]+|42\.5[NR]|52\.5[NR])\b", title, re.I
    )
    diameter = re.search(r"\b(\d+(?:\.\d+)?)\s*mm\b", title, re.I)
    if grade:
        spec["grade"] = grade.group(1).upper()
    if diameter:
        spec["diameter_mm"] = diameter.group(1)
    standard = re.search(r"\b(BS\s*4449|ASTM\s*A615|BDS\s*EN\s*197-1)\b", title, re.I)
    if standard:
        spec["standard"] = re.sub(r"\s+", " ", standard.group(1).upper())
    return spec


def currency_for(item, country):
    explicit = item.get("currency")
    if explicit in ("BDT", "USD", "EUR", "GBP", "INR", "CNY"):
        return explicit
    text = str(item.get("price", ""))
    for symbol, currency in (
        ("৳", "BDT"),
        ("BDT", "BDT"),
        ("Tk", "BDT"),
        ("£", "GBP"),
        ("€", "EUR"),
        ("₹", "INR"),
    ):
        if symbol in text:
            return currency
    if "$" in text and country == "US":
        return "USD"
    return None


def base_offer(title, supplier, price, currency, url, country, city, provider_id):
    weight = re.search(r"\b(\d+(?:\.\d+)?)\s*kg\s*(?:bag|pack)", title, re.I)
    per = re.search(r"(?:per|/)\s*(kg|tonne|ton|bag|m3|each)\b", title, re.I)
    unit = "bag" if weight else per.group(1).lower() if per else None
    if unit == "ton":
        unit = None  # US/short ton is not silently treated as a metric tonne.
    return {
        "title": title[:300],
        "supplier": supplier[:200],
        "provider_result_id": str(provider_id),
        "price": str(price) if price is not None else None,
        "currency": currency,
        "source_url": safe_url(url),
        "unit": unit,
        "package_weight_kg": weight.group(1) if weight else None,
        "quoted_quantity": "1",
        "minimum_quantity": "1",
        "specification": product_spec(title),
        "country": country,
        "city": city,
        "can_deliver": None,
        "delivery_days": None,
        "freight_basis": "UNKNOWN",
        "tax_basis": "UNKNOWN",
        "freight": None,
        "tax": None,
        "tax_recoverable": False,
        "handling": None,
        "other_cost": None,
        "rate_category": "MATERIAL",
        "verification": "INDICATIVE_PUBLIC_LISTING",
    }


class SerpApiProvider:
    name = "serpapi"

    @staticmethod
    def parse(data, request):
        if data.get("error"):
            raise ValueError(
                "Provider rejected the search; check location coverage and configuration"
            )
        offers = []
        for item in data.get("shopping_results", [])[:50]:
            try:
                offer = base_offer(
                    str(item.get("title", "")),
                    str(item.get("source", "Unknown merchant")),
                    item.get("extracted_price"),
                    currency_for(item, request["country"]),
                    item.get("product_link") or item.get("link"),
                    request["country"],
                    request["city"],
                    item.get("product_id", item.get("position", "")),
                )
                offer["delivery_description"] = str(item.get("delivery", ""))[:500]
            except (ValueError, TypeError, AttributeError):
                continue
            offer["source_link_kind"] = (
                "SHOPPING_PRODUCT"
                if "google." in str(offer.get("source_url"))
                else "PROVIDER_PRODUCT_LINK"
            )
            offers.append(offer)
        return offers

    async def search(self, request, settings):
        data = await api_json(
            "GET",
            "https://serpapi.com/search.json",
            settings,
            retry_safe=False,
            params={
                "engine": "google_shopping",
                "api_key": settings.serpapi_key,
                "q": request["query"],
                "gl": request["country"].lower(),
                "location": request["city"],
                "hl": "en",
            },
        )
        return self.parse(data, request)


class DataForSEOProvider:
    name = "dataforseo"

    @staticmethod
    def parse(data, request):
        offers = []
        for task in data.get("tasks", []):
            if task.get("status_code") not in (20000, 20100, 40601, 40602):
                raise ValueError("Shopping task failed; check provider status")
            for result in task.get("result") or []:
                for item in (result.get("items") or [])[:50]:
                    price = item.get("price") or {}
                    if not isinstance(price, dict):
                        price = {"current": price}
                    try:
                        offer = base_offer(
                            str(item.get("title", "")),
                            str(
                                item.get("seller")
                                or item.get("source")
                                or item.get("shop_name")
                                or "Unknown merchant"
                            ),
                            price.get("current"),
                            price.get("currency") or item.get("currency"),
                            item.get("url") or item.get("shopping_url"),
                            request["country"],
                            request["city"],
                            item.get("product_id") or item.get("data_docid") or "",
                        )
                        offers.append(offer)
                    except (ValueError, TypeError):
                        continue
        return offers

    async def submit(self, request, settings):
        auth = (settings.dataforseo_login, settings.dataforseo_password)
        locations = await api_json(
            "GET",
            "https://api.dataforseo.com/v3/merchant/google/locations",
            settings,
            auth=auth,
        )
        found = [
            loc
            for task in locations.get("tasks", [])
            for loc in task.get("result") or []
            if str(loc.get("country_iso_code", "")).upper() == request["country"]
        ]
        local = next(
            (
                v
                for v in found
                if request["city"].lower() in v.get("location_name", "").lower()
            ),
            None,
        )
        if not local:
            raise ValueError(
                "UNSUPPORTED_LOCATION: provider has no matching shopping location"
            )
        data = await api_json(
            "POST",
            "https://api.dataforseo.com/v3/merchant/google/products/task_post",
            settings,
            auth=auth,
            json=[
                {
                    "keyword": request["query"],
                    "location_code": local["location_code"],
                    "language_code": "en",
                    "priority": 1,
                }
            ],
        )
        task = (data.get("tasks") or [{}])[0]
        if task.get("status_code") != 20100 or not task.get("id"):
            raise ValueError("Provider did not accept the shopping task")
        return str(task["id"])

    async def retrieve(self, task_id, request, settings):
        if not re.fullmatch(r"[A-Za-z0-9-]{1,100}", task_id):
            raise ValueError("Invalid provider task ID")
        data = await api_json(
            "GET",
            f"https://api.dataforseo.com/v3/merchant/google/products/task_get/advanced/{task_id}",
            settings,
            auth=(settings.dataforseo_login, settings.dataforseo_password),
        )
        task = (data.get("tasks") or [{}])[0]
        if task.get("status_code") in (40601, 40602, 20100):
            return None
        return self.parse(data, request)


def demo_offers(material, request):
    spec = json.loads(material.specification_json)
    seed_price = {
        "tonne": "74000",
        "kg": "74",
        "bag": "720",
        "m3": "4500",
        "each": "15",
        "m2": "900",
    }.get(material.unit, "100")
    result = []
    for index, multiplier in enumerate((Decimal(1), Decimal("1.04"), Decimal("0.90"))):
        attrs = dict(spec)
        if index == 2:
            attrs["grade"] = "INCOMPATIBLE-DEMO-GRADE"
        result.append(
            {
                "title": material.name + (" — alternative grade" if index == 2 else ""),
                "supplier": f"Fictional Demo Supplier {index + 1}",
                "price": str(Decimal(seed_price) * multiplier),
                "currency": request["currency"],
                "unit": material.unit,
                "quoted_quantity": request["quantity"],
                "minimum_quantity": "1",
                "specification": attrs,
                "country": request["country"],
                "city": request["city"],
                "source_url": None,
                "can_deliver": True,
                "delivery_days": 3,
                "freight_basis": "INCLUDED",
                "tax_basis": "INCLUDED",
                "freight": "0",
                "tax": "0",
                "tax_recoverable": False,
                "handling": "0",
                "other_cost": "0",
                "rate_category": "MATERIAL",
                "verification": "SYNTHETIC_DEMO",
                "notes": "Synthetic catalogue; no current market offer or merchant claim.",
                "provider_result_id": f"demo-{material.id}-{index}",
            }
        )
    return result

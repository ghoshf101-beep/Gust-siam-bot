from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

from py import SUPPORTED_REGIONS, clean, extract_profile, fetch_profile

app = FastAPI(title="Free Fire ID API", version="1.1.0")


def enrich_skin_section(soup: BeautifulSoup, sections: dict[str, Any]) -> None:
    """Extract the named outfit/skin items when the public page exposes them."""
    text = clean(soup.get_text(" ", strip=True))
    labels = {
        "face_paint": r"Pintura Facial\s+(.+?)\s+Pegada",
        "legs": r"Pegada\s+(.+?)\s+Bardo do Vale",
        "head": r"Bardo do Vale\s+\(Cabeça\)\s+(.+?)\s+Assistente Congelado",
        "torso": r"Assistente Congelado\s+\(Torso\)\s+(.+?)\s+Comilão",
        "shoes": r"Comilão\s+\(Calçado\)\s+(.+?)\s+Coração Urbano",
        "mask": r"Coração Urbano\s+\(Máscara\)\s+(.+?)\s+Guilda",
    }
    skin_items = {}
    for key, pattern in labels.items():
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            skin_items[key] = clean(match.group(1))
    if skin_items:
        sections["skin"] = {"section": "Skin", "items": skin_items}


def complete_free_fire_data(profile: dict[str, Any], source_url: str, soup: BeautifulSoup) -> dict[str, Any]:
    sections = profile.get("sections", {})
    enrich_skin_section(soup, sections)
    return {
        "source_url": source_url,
        "sections": sections,
        "images": profile.get("images", []),
        "icons": profile.get("icons", []),
    }


@app.get("/")
def home() -> dict[str, str]:
    return {
        "name": "Free Fire ID API",
        "version": "1.1.0",
        "usage": "/api/free-fire-id?uid=2769409057&region=bd",
        "data": "All public profile sections, images and icons exposed by the source page",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/free-fire-id")
def free_fire_id(
    uid: str = Query(..., description="Free Fire numeric UID"),
    region: str = Query(..., description="Free Fire region code"),
) -> JSONResponse:
    uid = uid.strip()
    region = region.strip().lower()
    if not re.fullmatch(r"[0-9]{5,20}", uid):
        return JSONResponse(status_code=400, content={"ok": False, "error": "uid must contain 5 to 20 digits"})
    if region not in SUPPORTED_REGIONS:
        return JSONResponse(status_code=400, content={"ok": False, "error": "unsupported region"})
    try:
        source_url, raw_html = fetch_profile(uid, region)
    except Exception as exc:
        return JSONResponse(status_code=502, content={"ok": False, "error": "could not fetch profile", "details": str(exc)})
    soup = BeautifulSoup(raw_html, "html.parser")
    page_text = clean(soup.get_text(" ", strip=True))
    if any(term in page_text.lower() for term in ["jogador não encontrado", "perfil não encontrado", "não foi encontrado"]):
        return JSONResponse(status_code=404, content={"ok": False, "error": "profile not found", "uid": uid, "region": region.upper()})
    profile = extract_profile(soup, uid, region)
    return JSONResponse(content={
        "ok": True,
        "uid": uid,
        "region": region.upper(),
        "free_fire_id": complete_free_fire_data(profile, source_url, soup),
    })

# services/filter_config.py
"""Centrale filtercatalogus en normalisatie voor Nexi.

Bronnen:
- static/html/filtercollectie.html
- static/html/filteragenda.html
- Typesense-recordvelden die in de code/records worden gebruikt

Doel:
- natuurlijke taal en frontend-values normaliseren naar harde filterkeys
- dezelfde keys gebruiken voor Typesense en OBA URL/API
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, time
from typing import Any, Dict, Iterable, List, Optional, Tuple
from zoneinfo import ZoneInfo

AMSTERDAM_TZ = ZoneInfo("Europe/Amsterdam")

BOOK_INDELING: Dict[str, Dict[str, Any]] = {
    "prentenboeken baby": {
        "label": "Prentenboeken baby",
        "aliases": ["prentenboeken baby", "babyboeken", "boeken voor baby's", "boeken voor babies", "baby"],
        "typesense_field": "indeling",
        "typesense_value": "prentenboeken baby",
    },
    "prentenboeken tot 4 jaar": {
        "label": "Prentenboeken tot 4 jaar",
        "aliases": ["prentenboeken tot 4 jaar", "peuterboeken", "boeken voor peuters", "peuters", "peuter"],
        "typesense_field": "indeling",
        "typesense_value": "prentenboeken tot 4 jaar",
    },
    "prentenboeken vanaf 4 jaar": {
        "label": "Prentenboeken vanaf 4 jaar",
        "aliases": ["prentenboeken vanaf 4 jaar", "kleuterboeken", "boeken voor kleuters", "kleuters", "kleuter"],
        "typesense_field": "indeling",
        "typesense_value": "prentenboeken vanaf 4 jaar",
    },
    "fictie tot 9 jaar": {
        "label": "Fictie tot 9 jaar",
        "aliases": ["fictie tot 9 jaar", "boeken tot 9 jaar", "kinderen tot 9 jaar"],
        "typesense_field": "indeling",
        "typesense_value": "fictie tot 9 jaar",
    },
    "fictie 9 tot 12 jaar": {
        "label": "Fictie 9 tot 12 jaar",
        "aliases": ["fictie 9 tot 12 jaar", "9 tot 12 jaar", "9 t/m 12 jaar", "boeken 9 tot 12"],
        "typesense_field": "indeling",
        "typesense_value": "fictie 9 tot 12 jaar",
    },
    "fictie vanaf 12 jaar": {
        "label": "Fictie vanaf 12 jaar",
        "aliases": ["fictie vanaf 12 jaar", "vanaf 12 jaar", "12 plus", "12+", "twaalf plus"],
        "typesense_field": "indeling",
        "typesense_value": "fictie vanaf 12 jaar",
    },
    "fictie vanaf 15 jaar": {
        "label": "Fictie vanaf 15 jaar",
        "aliases": ["fictie vanaf 15 jaar", "vanaf 15 jaar", "15 plus", "15+", "vijftien plus"],
        "typesense_field": "indeling",
        "typesense_value": "fictie vanaf 15 jaar",
    },
    "fictie Volwassenen": {
        "label": "Fictie volwassenen",
        "aliases": ["fictie volwassenen", "volwassen fictie", "romans voor volwassenen", "volwassenen"],
        "typesense_field": "indeling",
        "typesense_value": "fictie Volwassenen",
    },
    "info tot 9 jaar": {
        "label": "Info tot 9 jaar",
        "aliases": ["info tot 9 jaar", "non-fictie tot 9 jaar", "informatieve boeken tot 9 jaar"],
        "typesense_field": "indeling",
        "typesense_value": "info tot 9 jaar",
    },
    "info vanaf 9 jaar": {
        "label": "Info vanaf 9 jaar",
        "aliases": ["info vanaf 9 jaar", "non-fictie vanaf 9 jaar", "informatieve boeken vanaf 9 jaar"],
        "typesense_field": "indeling",
        "typesense_value": "info vanaf 9 jaar",
    },
    "info volwassenen": {
        "label": "Info volwassenen",
        "aliases": ["info volwassenen", "non-fictie volwassenen", "informatieve boeken volwassenen"],
        "typesense_field": "indeling",
        "typesense_value": "info volwassenen",
    },
}

BOOK_LANGUAGES: Dict[str, Dict[str, Any]] = {
    "Nederlands": {"label": "Nederlands", "aliases": ["nederlands", "nederlandse", "nederlandstalig", "nl"], "typesense_field": "language", "typesense_value": "Nederlands"},
    "Engels": {"label": "Engels", "aliases": ["engels", "engelse", "engelstalig", "english"], "typesense_field": "language", "typesense_value": "Engels"},
    "Duits": {"label": "Duits", "aliases": ["duits", "duitse", "duitstalig", "german"], "typesense_field": "language", "typesense_value": "Duits"},
    "Frans": {"label": "Frans", "aliases": ["frans", "franse", "franstalig", "french"], "typesense_field": "language", "typesense_value": "Frans"},
    "Spaans": {"label": "Spaans", "aliases": ["spaans", "spaanse", "spaanstalig", "spanish"], "typesense_field": "language", "typesense_value": "Spaans"},
    "Turks": {"label": "Turks", "aliases": ["turks", "turkse", "turkstalig", "turkish"], "typesense_field": "language", "typesense_value": "Turks"},
    "Arabisch": {"label": "Arabisch", "aliases": ["arabisch", "arabische", "arabic"], "typesense_field": "language", "typesense_value": "Arabisch"},
}

AGENDA_LOCATIONS: Dict[str, Dict[str, Any]] = {
    "centrale-oba": {"label": "Centrale OBA (Oosterdok)", "aliases": ["centrale oba", "oba oosterdok", "oosterdok"], "oba_value": "Centrale OBA", "typesense_field": "gebouw", "typesense_value": "OBA Oosterdok"},
    "oba-banne": {"label": "OBA Banne", "aliases": ["oba banne", "de banne", "banne"], "oba_value": "OBA Banne", "typesense_field": "gebouw", "typesense_value": "OBA Banne"},
    "oba-bijlmer": {"label": "OBA Bijlmer", "aliases": ["oba bijlmer", "bijlmer"], "oba_value": "OBA Bijlmer", "typesense_field": "gebouw", "typesense_value": "OBA Bijlmer"},
    "oba-bos-en-lommer": {"label": "OBA Bos en Lommer", "aliases": ["oba bos en lommer", "bos en lommer"], "oba_value": "OBA Bos en Lommer", "typesense_field": "gebouw", "typesense_value": "OBA Bos en Lommer"},
    "oba-buitenveldert": {"label": "OBA Buitenveldert", "aliases": ["oba buitenveldert", "buitenveldert"], "oba_value": "OBA Buitenveldert", "typesense_field": "gebouw", "typesense_value": "OBA Buitenveldert"},
    "oba-cc-amstel": {"label": "OBA CC Amstel", "aliases": ["oba cc amstel", "cc amstel"], "oba_value": "OBA CC Amstel", "typesense_field": "gebouw", "typesense_value": "OBA CC Amstel"},
    "oba-de-hallen": {"label": "OBA De Hallen", "aliases": ["oba de hallen", "de hallen", "hallen"], "oba_value": "OBA De Hallen", "typesense_field": "gebouw", "typesense_value": "OBA De Hallen"},
    "oba-duivendrecht": {"label": "OBA Duivendrecht", "aliases": ["oba duivendrecht", "duivendrecht"], "oba_value": "OBA Duivendrecht", "typesense_field": "gebouw", "typesense_value": "OBA Duivendrecht"},
    "oba-geuzenveld": {"label": "OBA Geuzenveld", "aliases": ["oba geuzenveld", "geuzenveld"], "oba_value": "OBA Geuzenveld", "typesense_field": "gebouw", "typesense_value": "OBA Geuzenveld"},
    "oba-ijburg": {"label": "OBA IJburg", "aliases": ["oba ijburg", "ijburg"], "oba_value": "OBA IJburg", "typesense_field": "gebouw", "typesense_value": "OBA IJburg"},
    "oba-mercatorplein": {"label": "OBA Mercatorplein", "aliases": ["oba mercatorplein", "mercatorplein"], "oba_value": "OBA Mercatorplein", "typesense_field": "gebouw", "typesense_value": "OBA Mercatorplein"},
    "oba-molenwijk": {"label": "OBA Molenwijk", "aliases": ["oba molenwijk", "molenwijk"], "oba_value": "OBA Molenwijk", "typesense_field": "gebouw", "typesense_value": "OBA Molenwijk"},
    "oba-nextlab-kraaiennest": {"label": "OBA Next Lab Kraaiennest", "aliases": ["oba next lab kraaiennest", "next lab kraaiennest", "kraaiennest"], "oba_value": "OBA Next Lab Kraaiennest", "typesense_field": "gebouw", "typesense_value": "OBA Next Lab Kraaiennest"},
    "oba-nextlab-sluisbuurt": {"label": "OBA Next Lab Sluisbuurt", "aliases": ["oba next lab sluisbuurt", "next lab sluisbuurt", "sluisbuurt"], "oba_value": "OBA Next Lab Sluisbuurt", "typesense_field": "gebouw", "typesense_value": "OBA Next Lab Sluisbuurt"},
    "oba-olympisch-kwartier": {"label": "OBA Olympisch Kwartier", "aliases": ["oba olympisch kwartier", "olympisch kwartier"], "oba_value": "OBA Olympisch Kwartier", "typesense_field": "gebouw", "typesense_value": "OBA Olympisch Kwartier"},
    "oba-osdorp": {"label": "OBA Osdorp", "aliases": ["oba osdorp", "osdorp"], "oba_value": "OBA Osdorp", "typesense_field": "gebouw", "typesense_value": "OBA Osdorp"},
    "oba-ouderkerk": {"label": "OBA Ouderkerk", "aliases": ["oba ouderkerk", "ouderkerk"], "oba_value": "OBA Ouderkerk", "typesense_field": "gebouw", "typesense_value": "OBA Ouderkerk"},
    "oba-postjesweg": {"label": "OBA Postjesweg", "aliases": ["oba postjesweg", "postjesweg"], "oba_value": "OBA Postjesweg", "typesense_field": "gebouw", "typesense_value": "OBA Postjesweg"},
    "oba-punt-ganzenhoef": {"label": "OBA punt Ganzenhoef", "aliases": ["oba punt ganzenhoef", "punt ganzenhoef", "ganzenhoef"], "oba_value": "OBA punt Ganzenhoef", "typesense_field": "gebouw", "typesense_value": "OBA punt Ganzenhoef"},
    "oba-reigersbos": {"label": "OBA Reigersbos", "aliases": ["oba reigersbos", "reigersbos"], "oba_value": "OBA Reigersbos", "typesense_field": "gebouw", "typesense_value": "OBA Reigersbos"},
    "oba-roelof-hartplein": {"label": "OBA Roelof Hartplein", "aliases": ["oba roelof hartplein", "roelof hartplein"], "oba_value": "OBA Roelof Hartplein", "typesense_field": "gebouw", "typesense_value": "OBA Roelof Hartplein"},
    "oba-slotermeer": {"label": "OBA Slotermeer", "aliases": ["oba slotermeer", "slotermeer"], "oba_value": "OBA Slotermeer", "typesense_field": "gebouw", "typesense_value": "OBA Slotermeer"},
    "oba-spaarndammerbuurt": {"label": "OBA Spaarndammerbuurt", "aliases": ["oba spaarndammerbuurt", "spaarndammerbuurt"], "oba_value": "OBA Spaarndammerbuurt", "typesense_field": "gebouw", "typesense_value": "OBA Spaarndammerbuurt"},
    "oba-staatsliedenbuurt": {"label": "OBA Staatsliedenbuurt", "aliases": ["oba staatsliedenbuurt", "staatsliedenbuurt"], "oba_value": "OBA Staatsliedenbuurt", "typesense_field": "gebouw", "typesense_value": "OBA Staatsliedenbuurt"},
    "oba-van-der-pek": {"label": "OBA Van der Pek", "aliases": ["oba van der pek", "van der pek"], "oba_value": "OBA Van der Pek", "typesense_field": "gebouw", "typesense_value": "OBA Van der Pek"},
    "oba-waterlandplein": {"label": "OBA Waterlandplein", "aliases": ["oba waterlandplein", "waterlandplein"], "oba_value": "OBA Waterlandplein", "typesense_field": "gebouw", "typesense_value": "OBA Waterlandplein"},
    "oba-weesp": {"label": "OBA Weesp", "aliases": ["oba weesp", "weesp"], "oba_value": "OBA Weesp", "typesense_field": "gebouw", "typesense_value": "OBA Weesp"},
}

AGENDA_AGES: Dict[str, Dict[str, Any]] = {
    "0-3": {"label": "0 t/m 3 jaar", "aliases": ["0 t/m 3", "0 tot 3", "baby", "peuter", "peuters"], "oba_value": "0-3", "typesense_field": "leeftijdscategorie", "typesense_value": "0 t/m 3 jaar"},
    "4-12": {"label": "4 t/m 12 jaar", "aliases": ["4 t/m 12", "4 tot 12", "kind", "kinderen"], "oba_value": "4-12", "typesense_field": "leeftijdscategorie", "typesense_value": "4 t/m 12 jaar"},
    "13-18": {"label": "13 t/m 18 jaar", "aliases": ["13 t/m 18", "13 tot 18", "tieners", "jongeren"], "oba_value": "13-18", "typesense_field": "leeftijdscategorie", "typesense_value": "13 t/m 18 jaar"},
    "19-26": {"label": "19 t/m 26 jaar", "aliases": ["19 t/m 26", "19 tot 26", "jongvolwassenen", "studenten"], "oba_value": "19-26", "typesense_field": "leeftijdscategorie", "typesense_value": "19 t/m 26 jaar"},
    "27-66": {"label": "27 t/m 66 jaar", "aliases": ["27 t/m 66", "27 tot 66", "volwassenen", "volwassene"], "oba_value": "27-66", "typesense_field": "leeftijdscategorie", "typesense_value": "27 t/m 66 jaar"},
    "67+": {"label": "67 jaar en ouder", "aliases": ["67+", "67 jaar en ouder", "senioren", "ouderen"], "oba_value": "67+", "typesense_field": "leeftijdscategorie", "typesense_value": "67 jaar en ouder"},
}

AGENDA_WHEN: Dict[str, Dict[str, Any]] = {
    "a_today": {"label": "Vandaag", "aliases": ["vandaag"], "oba_value": "a_today"},
    "a_tomorrow": {"label": "Morgen", "aliases": ["morgen"], "oba_value": "a_tomorrow"},
    "b_upcomingweekend": {"label": "Komend weekend", "aliases": ["komend weekend", "dit weekend", "weekend"], "oba_value": "b_upcomingweekend"},
    "c_nextweek": {"label": "Volgende week", "aliases": ["volgende week"], "oba_value": "c_nextweek"},
    "d_thismonth": {"label": "Deze maand", "aliases": ["deze maand"], "oba_value": "d_thismonth"},
    "e_nextmonth": {"label": "Volgende maand", "aliases": ["volgende maand"], "oba_value": "e_nextmonth"},
    "f_next3month": {"label": "Komende 3 maanden", "aliases": ["komende 3 maanden", "volgende 3 maanden", "drie maanden"], "oba_value": "f_next3month"},
    "g_thisyear": {"label": "Dit jaar", "aliases": ["dit jaar"], "oba_value": "g_thisyear"},
    "h_nextyear": {"label": "Volgend jaar", "aliases": ["volgend jaar"], "oba_value": "h_nextyear"},
}

AGENDA_TYPES: Dict[str, Dict[str, Any]] = {
    "boekenclub": {"label": "Boekenclub", "aliases": ["boekenclub", "boekenclubs"], "oba_value": "boekenclub", "typesense_field": "type_activiteit", "typesense_value": "Boekenclub"},
    "expositie": {"label": "Expositie", "aliases": ["expositie", "tentoonstelling"], "oba_value": "expositie", "typesense_field": "type_activiteit", "typesense_value": "Expositie"},
    "film": {"label": "Film", "aliases": ["film", "films"], "oba_value": "film", "typesense_field": "type_activiteit", "typesense_value": "Film"},
    "hulp-ontwikkeling": {"label": "Hulp & Ontwikkeling", "aliases": ["hulp ontwikkeling", "hulp en ontwikkeling", "hulp & ontwikkeling"], "oba_value": "hulp-ontwikkeling", "typesense_field": "type_activiteit", "typesense_value": "Hulp & Ontwikkeling"},
    "muziek": {"label": "Muziek", "aliases": ["muziek", "concert"], "oba_value": "muziek", "typesense_field": "type_activiteit", "typesense_value": "Muziek"},
    "ontmoeten": {"label": "Ontmoeten", "aliases": ["ontmoeten", "ontmoeting"], "oba_value": "ontmoeten", "typesense_field": "type_activiteit", "typesense_value": "Ontmoeten"},
    "overig": {"label": "Overig", "aliases": ["overig"], "oba_value": "overig", "typesense_field": "type_activiteit", "typesense_value": "Overig"},
    "speciaal": {"label": "Speciaal", "aliases": ["speciaal"], "oba_value": "speciaal", "typesense_field": "type_activiteit", "typesense_value": "Speciaal"},
    "talk": {"label": "Talk", "aliases": ["talk", "lezing", "gesprek"], "oba_value": "talk", "typesense_field": "type_activiteit", "typesense_value": "Talk"},
    "theater": {"label": "Theater", "aliases": ["theater", "voorstelling"], "oba_value": "theater", "typesense_field": "type_activiteit", "typesense_value": "Theater"},
    "voorlezen": {"label": "Voorlezen", "aliases": ["voorlezen", "voorleesactiviteit", "voorleesmiddag"], "oba_value": "voorlezen", "typesense_field": "type_activiteit", "typesense_value": "Voorlezen"},
    "workshop": {"label": "Workshop", "aliases": ["workshop", "workshops"], "oba_value": "workshop", "typesense_field": "type_activiteit", "typesense_value": "Workshop"},
}

BOOK_FILTERS = {"indeling": BOOK_INDELING, "language": BOOK_LANGUAGES}
AGENDA_FILTERS = {"waar": AGENDA_LOCATIONS, "leeftijd": AGENDA_AGES, "wanneer": AGENDA_WHEN, "type_activiteit": AGENDA_TYPES}


def norm_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("_", "-")
    text = re.sub(r"[()\[\]{}.,;:!?]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _alias_patterns(alias: str) -> List[str]:
    n = norm_text(alias)
    variants = {n, n.replace("-", " "), n.replace(" ", "-")}
    return [v for v in variants if v]


def _matches_alias(haystack: str, alias: str) -> bool:
    if not haystack or not alias:
        return False
    for variant in _alias_patterns(alias):
        if re.search(r"(?<!\w)" + re.escape(variant) + r"(?!\w)", haystack):
            return True
    return False


def resolve_option(options: Dict[str, Dict[str, Any]], value: Any) -> Optional[Tuple[str, Dict[str, Any]]]:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    if raw in options:
        return raw, options[raw]
    key = norm_text(raw)
    for opt_key, cfg in options.items():
        candidates = [opt_key, cfg.get("label"), cfg.get("typesense_value"), cfg.get("oba_value")] + list(cfg.get("aliases") or [])
        for candidate in candidates:
            if key == norm_text(candidate):
                return opt_key, cfg
    return None


def find_option_in_text(options: Dict[str, Dict[str, Any]], text: Any) -> Optional[Tuple[str, Dict[str, Any]]]:
    haystack = norm_text(text)
    if not haystack:
        return None

    # Langste aliases eerst zodat "oba bos en lommer" wint boven kortere deelmatches.
    candidates: List[Tuple[int, str, str, Dict[str, Any]]] = []
    for opt_key, cfg in options.items():
        values = [opt_key, cfg.get("label"), cfg.get("typesense_value"), cfg.get("oba_value")] + list(cfg.get("aliases") or [])
        for v in values:
            if not v:
                continue
            candidates.append((len(norm_text(v)), opt_key, str(v), cfg))
    candidates.sort(reverse=True, key=lambda item: item[0])

    for _, opt_key, alias, cfg in candidates:
        if _matches_alias(haystack, alias):
            return opt_key, cfg
    return None


def _dedupe_filters(items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []
    for item in items:
        sig = (item.get("domain"), item.get("filter"), item.get("key"), item.get("field"), item.get("value"))
        if sig in seen:
            continue
        seen.add(sig)
        out.append(item)
    return out


def _ts_quote(value: Any) -> str:
    text = str(value).replace("`", "\\`")
    return f"`{text}`"


def _ts_exact(field: str, value: Any) -> str:
    return f"{field}:={_ts_quote(value)}"


def build_typesense_filter(parts: Iterable[str]) -> str:
    return " && ".join([p for p in parts if p])


def normalize_book_filters(filters: Optional[Dict[str, Any]] = None, text: Optional[str] = None) -> Dict[str, Any]:
    filters = filters or {}
    text = text or ""
    normalized: List[Dict[str, Any]] = []

    indeling_values: List[str] = []
    for key_name in ("indeling", "fictie", "nonfictie", "content_type_value"):
        raw = filters.get(key_name)
        if isinstance(raw, list):
            indeling_values.extend([str(v) for v in raw if v])
        elif raw:
            indeling_values.append(str(raw))

    for raw in indeling_values:
        resolved = resolve_option(BOOK_INDELING, raw)
        if resolved:
            key, cfg = resolved
            normalized.append({"domain": "books", "filter": "indeling", "key": key, "label": cfg["label"], "field": cfg["typesense_field"], "value": cfg["typesense_value"]})

    raw_language = filters.get("language") or filters.get("taal")
    if raw_language:
        resolved = resolve_option(BOOK_LANGUAGES, raw_language)
        if resolved:
            key, cfg = resolved
            normalized.append({"domain": "books", "filter": "language", "key": key, "label": cfg["label"], "field": cfg["typesense_field"], "value": cfg["typesense_value"]})

    # Natural-language fallback: alleen als filter nog niet expliciet aanwezig is.
    if text:
        if not any(f["filter"] == "language" for f in normalized):
            resolved = find_option_in_text(BOOK_LANGUAGES, text)
            if resolved:
                key, cfg = resolved
                normalized.append({"domain": "books", "filter": "language", "key": key, "label": cfg["label"], "field": cfg["typesense_field"], "value": cfg["typesense_value"]})
        if not any(f["filter"] == "indeling" for f in normalized):
            resolved = find_option_in_text(BOOK_INDELING, text)
            if resolved:
                key, cfg = resolved
                normalized.append({"domain": "books", "filter": "indeling", "key": key, "label": cfg["label"], "field": cfg["typesense_field"], "value": cfg["typesense_value"]})

    normalized = _dedupe_filters(normalized)
    indeling = [f["value"] for f in normalized if f["filter"] == "indeling"]
    language = next((f["value"] for f in normalized if f["filter"] == "language"), None)
    parts: List[str] = []
    if indeling:
        parts.append("(" + " || ".join([_ts_exact("indeling", v) for v in indeling]) + ")")
    if language:
        parts.append(_ts_exact("language", language))
    return {"normalized_filters": normalized, "filter_by": build_typesense_filter(parts)}


def _agenda_range_bounds(key: str) -> Optional[Tuple[int, int]]:
    now = datetime.now(AMSTERDAM_TZ)
    today = datetime.combine(now.date(), time.min, tzinfo=AMSTERDAM_TZ)
    tomorrow = today + timedelta(days=1)

    if key == "a_today":
        start, end = today, tomorrow
    elif key == "a_tomorrow":
        start, end = tomorrow, tomorrow + timedelta(days=1)
    elif key == "b_upcomingweekend":
        # Eerstvolgende zaterdag-zondag vanaf vandaag.
        days_until_sat = (5 - today.weekday()) % 7
        start = today + timedelta(days=days_until_sat)
        end = start + timedelta(days=2)
    elif key == "c_nextweek":
        next_monday = today + timedelta(days=(7 - today.weekday()))
        start, end = next_monday, next_monday + timedelta(days=7)
    elif key == "d_thismonth":
        start = today.replace(day=1)
        end = (start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1))
    elif key == "e_nextmonth":
        this_month = today.replace(day=1)
        start = this_month.replace(year=this_month.year + 1, month=1) if this_month.month == 12 else this_month.replace(month=this_month.month + 1)
        end = start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1)
    elif key == "f_next3month":
        start = today
        end = today + timedelta(days=93)
    elif key == "g_thisyear":
        start = today
        end = datetime(today.year + 1, 1, 1, tzinfo=AMSTERDAM_TZ)
    elif key == "h_nextyear":
        start = datetime(today.year + 1, 1, 1, tzinfo=AMSTERDAM_TZ)
        end = datetime(today.year + 2, 1, 1, tzinfo=AMSTERDAM_TZ)
    else:
        return None
    return int(start.timestamp()), int(end.timestamp())


def normalize_agenda_filters(filters: Optional[Dict[str, Any]] = None, text: Optional[str] = None) -> Dict[str, Any]:
    filters = filters or {}
    text = text or ""
    specs = [
        ("waar", AGENDA_LOCATIONS),
        ("leeftijd", AGENDA_AGES),
        ("wanneer", AGENDA_WHEN),
        ("type_activiteit", AGENDA_TYPES),
    ]
    aliases = {
        "waar": ["waar", "location", "locatie"],
        "leeftijd": ["leeftijd", "age", "leeftijdscategorie"],
        "wanneer": ["wanneer", "date", "datum"],
        "type_activiteit": ["type_activiteit", "type", "activity_type", "activiteitstype"],
    }
    normalized: List[Dict[str, Any]] = []

    for filter_name, options in specs:
        raw = None
        for alias in aliases[filter_name]:
            if filters.get(alias):
                raw = filters.get(alias)
                break
        resolved = resolve_option(options, raw) if raw else None
        if not resolved and text:
            resolved = find_option_in_text(options, text)
        if not resolved:
            continue
        key, cfg = resolved
        item: Dict[str, Any] = {"domain": "agenda", "filter": filter_name, "key": key, "label": cfg["label"], "oba_value": cfg.get("oba_value")}
        if cfg.get("typesense_field"):
            item.update({"field": cfg["typesense_field"], "value": cfg["typesense_value"]})
        if filter_name == "wanneer":
            bounds = _agenda_range_bounds(key)
            if bounds:
                item["field"] = "starttijd_ts"
                item["range"] = {"gte": bounds[0], "lt": bounds[1]}
        normalized.append(item)

    normalized = _dedupe_filters(normalized)
    parts: List[str] = []
    for item in normalized:
        if item.get("range"):
            rng = item["range"]
            parts.append(f"{item['field']}:>={rng['gte']} && {item['field']}:<{rng['lt']}")
        elif item.get("field") and item.get("value") is not None:
            parts.append(_ts_exact(item["field"], item["value"]))
    return {"normalized_filters": normalized, "filter_by": build_typesense_filter(parts)}


def parse_legacy_filter_string(filter_string: str) -> Dict[str, Any]:
    """Parse oude frontendstrings zoals 'Locatie: oba-banne||Wanneer: a_today'."""
    out: Dict[str, Any] = {}
    for part in (filter_string or "").split("||"):
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        k = norm_text(key).replace(" ", "_")
        v = value.strip()
        if not v:
            continue
        if k in ("locatie", "location"):
            out["waar"] = v
        elif k in ("leeftijd", "age"):
            out["leeftijd"] = v
        elif k in ("wanneer", "date", "datum"):
            out["wanneer"] = v
        elif k in ("type", "activiteitstype"):
            out["type_activiteit"] = v
        elif k == "indeling":
            out["indeling"] = v
        elif k in ("taal", "language"):
            out["language"] = v
        else:
            out[k] = v
    return out


def frontend_filter_payload(domain: str) -> Dict[str, Any]:
    if domain == "collection":
        return {
            "domain": "collection",
            "groups": [
                {"key": "fictie", "label": "Fictie", "type": "radio", "options": [{"value": k, "label": v["label"]} for k, v in BOOK_INDELING.items() if not k.startswith("info ")]},
                {"key": "nonfictie", "label": "Non-fictie", "type": "radio", "options": [{"value": k, "label": v["label"]} for k, v in BOOK_INDELING.items() if k.startswith("info ")]},
                {"key": "language", "label": "Taal", "type": "radio", "options": [{"value": k, "label": v["label"]} for k, v in BOOK_LANGUAGES.items()]},
            ],
        }
    if domain == "agenda":
        return {
            "domain": "agenda",
            "groups": [
                {"key": "waar", "label": "Locatie", "type": "select", "empty_label": "Alle locaties", "options": [{"value": k, "label": v["label"]} for k, v in AGENDA_LOCATIONS.items()]},
                {"key": "leeftijd", "label": "Leeftijdscategorie", "type": "select", "empty_label": "Alle leeftijden", "options": [{"value": k, "label": v["label"]} for k, v in AGENDA_AGES.items()]},
                {"key": "wanneer", "label": "Wanneer", "type": "select", "empty_label": "Alle data", "options": [{"value": k, "label": v["label"]} for k, v in AGENDA_WHEN.items()]},
                {"key": "type_activiteit", "label": "Activiteitstype", "type": "select", "empty_label": "Alle types", "options": [{"value": k, "label": v["label"]} for k, v in AGENDA_TYPES.items()]},
            ],
        }
    return {"domain": domain, "groups": []}

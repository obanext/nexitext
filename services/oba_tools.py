import re
import urllib.parse as ul
from typing import Any, Dict, List, Optional

from services.oba_config import (
    COLLECTION_BOOKS,
    COLLECTION_BOOKS_KN,
    COLLECTION_FAQ,
    COLLECTION_EVENTS,
)
from services.filter_config import (
    normalize_book_filters,
    normalize_agenda_filters,
    parse_legacy_filter_string,
)

FICTION_MAP = {
    "baby": ["prentenboeken baby"],
    "peuter": ["prentenboeken tot 4 jaar"],
    "kleuter": ["prentenboeken vanaf 4 jaar"],
    "kind": ["fictie tot 9 jaar", "fictie 9 tot 12 jaar"],
    "jeugd": ["fictie 9 tot 12 jaar", "fictie vanaf 12 jaar"],
    "oudere_jeugd": ["fictie vanaf 15 jaar"],
    "volwassen": ["fictie Volwassenen"],
}

NONFICTION_MAP = {
    "kind": ["info tot 9 jaar"],
    "jeugd": ["info vanaf 9 jaar"],
    "oudere_jeugd": ["info volwassenen"],
    "volwassen": ["info volwassenen"],
}

AUDIENCE_ALIASES = {
    "baby": ["baby", "baby's", "babies"],
    "peuter": ["peuter", "peuters"],
    "kleuter": ["kleuter", "kleuters"],
    "kind": ["kind", "kinderen"],
    "jeugd": ["jeugd", "jongeren", "tieners"],
    "oudere_jeugd": ["oudere jeugd", "vanaf 15", "15+", "15 plus"],
    "volwassen": ["volwassen", "volwassenen"],
}

CONTENT_TYPE_ALIASES = {
    "fictie": ["fictie", "verhalen", "roman", "romans", "leesboeken"],
    "nonfictie": ["non-fictie", "nonfictie", "informatieboeken", "informatieve boeken", "info boeken", "info-boeken"],
}


def _audience_is_mentioned(audience: Optional[str], text: str) -> bool:
    """Accepteer doelgroep alleen in doelgroepcontext.

    Daardoor telt "boeken voor baby's" wel als doelgroep, maar "baby dinosaurussen" niet.
    """
    if not audience or not text:
        return False
    aliases = AUDIENCE_ALIASES.get(audience, [])
    haystack = text.lower()
    for alias in aliases:
        a = re.escape(alias.lower())
        patterns = [
            rf"\bvoor\s+(?:de\s+)?{a}\b",
            rf"\bvoor\s+(?:kinderen|lezers)?\s*(?:van\s+)?{a}\b",
            rf"\b{a}boeken\b",
            rf"\bboeken\s+voor\s+{a}\b",
        ]
        if any(re.search(pattern, haystack) for pattern in patterns):
            return True
    return False


def _content_type_is_mentioned(content_type: Optional[str], text: str) -> bool:
    if not content_type or not text:
        return False
    aliases = CONTENT_TYPE_ALIASES.get(content_type, [])
    haystack = text.lower()
    return any(re.search(r"(?<!\w)" + re.escape(alias.lower()) + r"(?!\w)", haystack) for alias in aliases)


def _clean_semantic_book_query(query: str, original_text: str) -> str:
    """Verwijder duidelijke zoek-/doelgroepfrases uit q, behoud het onderwerp.

    Voorbeeld: "boeken voor baby's over slapen" -> "slapen".
    "baby dinosaurussen" blijft intact omdat daar geen doelgroepconstructie met "voor" staat.
    """
    q = (query or "").strip()
    source = (original_text or q).strip()
    if not q:
        return q
    if re.search(r"\bover\s+(.+)$", source, re.I):
        topic = re.search(r"\bover\s+(.+)$", source, re.I).group(1).strip()
        if topic:
            return topic
    return q


def _merge_filter_by(*parts: Optional[str]) -> str:
    return " && ".join([p for p in parts if p])


def _looks_author(text: str) -> bool:
    return bool(re.search(r"\b(auteur|schrijver|door|van)\b", text, re.I))


def _looks_title(text: str) -> bool:
    return bool(re.search(r"\btitel\b|\".+\"|\'[^\']+\'", text))


def _coerce_filters(filters: Optional[Dict[str, Any]], legacy_filter_string: Optional[str] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if isinstance(filters, dict):
        out.update(filters)
    if legacy_filter_string:
        out.update(parse_legacy_filter_string(legacy_filter_string))
    return out


def _build_search_params(
    user_query: str,
    query_by_choice: Optional[str] = None,
    vector_alpha: Optional[float] = None,
    location_kraaiennest: Optional[bool] = False,
    audience: Optional[str] = None,
    content_type: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
    filter_source: str = "llm",
    original_text: Optional[str] = None,
) -> Dict[str, Any]:

    text = (user_query or "").strip()
    validation_text = (original_text or user_query or "").strip()
    filters = _coerce_filters(filters)
    trust_explicit_filters = (filter_source == "frontend")

    if query_by_choice:
        qb = query_by_choice
    else:
        # Gebruik de originele gebruikerszin voor intentieherkenning. De toolrouter kan
        # user_query al hebben teruggebracht tot alleen "Orwell", waardoor "van" verdwijnt.
        intent_text = validation_text or text
        if _looks_author(intent_text) and not _looks_title(intent_text):
            qb = "main_author"
        elif _looks_title(intent_text) and not _looks_author(intent_text):
            qb = "short_title"
        else:
            qb = "embedding"

    if qb.startswith("embedding"):
        alpha = vector_alpha if isinstance(vector_alpha, (int, float)) else (0.4 if "," in qb else 0.8)
        vq = f"embedding:([], alpha: {alpha})"
    else:
        vq = ""

    # Doelgroep-logica: accepteer een LLM-audience alleen als die doelgroep ook aantoonbaar
    # in de originele gebruikerszin staat. Zonder content_type betekent dit bestaande
    # codecontract: beide (fictie + non-fictie).
    trusted_indeling_values: List[str] = []
    if audience and _audience_is_mentioned(audience, validation_text):
        effective_content_type = content_type or "beide"
        if effective_content_type in ("fictie", "beide"):
            trusted_indeling_values += FICTION_MAP.get(audience, [])
        if effective_content_type in ("nonfictie", "beide"):
            trusted_indeling_values += NONFICTION_MAP.get(audience, [])
    elif content_type and _content_type_is_mentioned(content_type, validation_text):
        # Expliciete materiaalsoort zonder doelgroep: gebruik alle harde indelingen binnen die soort.
        # Voorbeeld: "informatieboeken over vulkanen" -> alle info-categorieën.
        if content_type == "fictie":
            for vals in FICTION_MAP.values():
                trusted_indeling_values += vals
        elif content_type == "nonfictie":
            for vals in NONFICTION_MAP.values():
                trusted_indeling_values += vals

    normalized = normalize_book_filters(
        filters=filters,
        text=validation_text,
        trust_explicit_filters=trust_explicit_filters,
        trusted_indeling_values=trusted_indeling_values,
    )
    fb = normalized["filter_by"]
    books = COLLECTION_BOOKS_KN if location_kraaiennest else COLLECTION_BOOKS

    q_text = _clean_semantic_book_query(text, validation_text) if qb.startswith("embedding") else text

    return {
        "q": q_text,
        "collection": books,
        "query_by": qb,
        "vector_query": vq,
        "filter_by": fb,
        "normalized_filters": normalized["normalized_filters"],
        "Message": "Ik heb voor je gezocht en deze boeken gevonden",
        "STATUS": "KLAAR",
    }


def _build_compare_params(
    comparison_query: str,
    original: Optional[str] = None,
    mode: Optional[str] = None,
    vector_alpha: Optional[float] = None,
    location_kraaiennest: Optional[bool] = False,
    filters: Optional[Dict[str, Any]] = None,
    filter_source: str = "llm",
    original_text: Optional[str] = None,
) -> Dict[str, Any]:
    """Compare gebruikt dezelfde boekroute, maar met eigen Message en genormaliseerde filters.

    De huidige tooldefinitie bevat geen harde exclude-velden zoals ppn/id. Daarom wordt hier geen
    niet-bestaand uitsluitfilter geconstrueerd; filters die wel bestaan worden deterministisch toegepast.
    """
    text = (comparison_query or "").strip()
    validation_text = (original_text or comparison_query or "").strip()
    filters = _coerce_filters(filters)
    trust_explicit_filters = (filter_source == "frontend")
    alpha = vector_alpha if isinstance(vector_alpha, (int, float)) else 0.8
    normalized = normalize_book_filters(filters=filters, text=validation_text, trust_explicit_filters=trust_explicit_filters)

    return {
        "q": text,
        "collection": COLLECTION_BOOKS_KN if location_kraaiennest else COLLECTION_BOOKS,
        "query_by": "embedding",
        "vector_query": f"embedding:([], alpha: {alpha})",
        "filter_by": normalized["filter_by"],
        "normalized_filters": normalized["normalized_filters"],
        "comparison": {"original": original, "mode": mode},
        "Message": "Ik heb vergelijkbare boeken gevonden",
        "STATUS": "KLAAR",
    }


def _agenda_filters_from_args(
    waar: Optional[str],
    leeftijd: Optional[str],
    wanneer: Optional[str],
    type_activiteit: Optional[str],
) -> Dict[str, Any]:
    filters: Dict[str, Any] = {}
    if waar:
        filters["waar"] = waar
    if leeftijd:
        filters["leeftijd"] = leeftijd
    if wanneer:
        filters["wanneer"] = wanneer
    if type_activiteit:
        filters["type_activiteit"] = type_activiteit
    return filters


def _build_agenda_query(
    scenario: str,
    waar: Optional[str] = None,
    leeftijd: Optional[str] = None,
    wanneer: Optional[str] = None,
    type_activiteit: Optional[str] = None,
    agenda_text: Optional[str] = None,
    filter_source: str = "llm",
    original_text: Optional[str] = None,
) -> Dict[str, Any]:

    scenario = (scenario or "").upper().strip()
    text = (agenda_text or "").strip()
    validation_text = (original_text or agenda_text or "").strip()
    trust_explicit_filters = (filter_source == "frontend")
    normalized = normalize_agenda_filters(
        filters=_agenda_filters_from_args(waar, leeftijd, wanneer, type_activiteit),
        text=validation_text,
        trust_explicit_filters=trust_explicit_filters,
    )
    normalized_filters = normalized["normalized_filters"]

    # Scenario A: directe OBA URL/API. Gebruik alleen de OBA-facetwaarden uit de centrale catalogus.
    if scenario == "A":
        base_front = "https://oba.nl/nl/agenda/volledige-agenda"
        qs = []
        facets = []

        for item in normalized_filters:
            fname = item.get("filter")
            oba_value = item.get("oba_value") or item.get("key")
            if not oba_value:
                continue
            if fname == "waar":
                qs.append("waar=" + ul.quote_plus(f"/root/OBA/{oba_value}"))
                facets.append("facet=waar%28" + ul.quote_plus(f"/root/OBA/{oba_value}") + "%29")
            elif fname == "leeftijd":
                qs.append("leeftijd=" + ul.quote_plus(oba_value))
                facets.append("facet=leeftijd%28" + ul.quote_plus(oba_value) + "%29")
            elif fname == "wanneer":
                qs.append("Wanneer=" + ul.quote_plus(oba_value))
                facets.append("facet=wanneer%28" + ul.quote_plus(oba_value) + "%29")
            elif fname == "type_activiteit":
                qs.append("type_activiteit=" + ul.quote_plus(oba_value))
                facets.append("facet=type_activiteit%28" + ul.quote_plus(oba_value) + "%29")

        url = base_front + ("?" + "&".join(qs) if qs else "")
        base_api = "https://zoeken.oba.nl/api/v1/search/?q=table:evenementen&refine=true"
        api = base_api + ("&" + "&".join(facets) if facets else "")

        return {
            "URL": url,
            "API": api,
            "normalized_filters": normalized_filters,
            "Message": "Ik heb deze activiteiten gevonden",
            "STATUS": "KLAAR",
        }

    # Scenario B / fallback: exploratief via Typesense, maar harde filters blijven actief zodra herkenbaar.
    return {
        "q": text,
        "collection": COLLECTION_EVENTS,
        "query_by": "embedding",
        "vector_query": "embedding:([], alpha: 0.8)",
        "filter_by": normalized["filter_by"],
        "normalized_filters": normalized_filters,
        "Message": "Ik zoek in de agenda",
        "STATUS": "KLAAR",
    }


def _build_faq_params(user_query: str) -> Dict[str, Any]:
    # FAQ-schema is in deze code niet volledig genoeg om harde filters veilig af te dwingen.
    return {
        "q": user_query,
        "collection": COLLECTION_FAQ,
        "query_by": "embedding",
        "vector_query": "embedding:([], alpha: 0.8)",
        "filter_by": "",
        "normalized_filters": [],
        "STATUS": "KLAAR",
    }


TOOL_IMPLS = {
    "build_search_params": _build_search_params,
    "build_compare_params": _build_compare_params,
    "build_agenda_query": _build_agenda_query,
    "build_faq_params": _build_faq_params,
}

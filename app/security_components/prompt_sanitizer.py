import re
import html
import unicodedata
from typing import Optional, Dict, Any

# --- Config ---
MAX_LENGTH = 2000
HIGH_RISK_THRESHOLD = 0.6  # sopra questo valore -> bloccare
MEDIUM_RISK_THRESHOLD = 0.1  # sopra questo -> warning

# Patterns estesi
PATTERNS = {
    "explicit_injection": [
        r"ignore\s+(all\s+)?(previous\s+)?instructions",
        r"disregard\s+(the\s+)?rules",
        r"reveal\s+(system|hidden)\s+(prompt|instruction)",
        r"act\s+as\s+(an?\s+)?(admin|developer|hacker)",
        r"enable\s+developer\s+mode",
        r"(inject|override)\s+(the\s+)?prompt",
        r"(system|assistant)\s*:",
    ],
    "script_html": [
        r"<\s*script.*?>.*?<\s*/\s*script\s*>",  # tag script
        r"on\w+\s*=",  # attributi evento come onclick=
        r"<\s*iframe.*?>", r"<\s*img.*?on\w+\s*=",
    ],
    "code_exec": [
        r"\b(exec|eval|compile|subprocess|os\.system|popen|system\(|shell_exec|`.+?`)\b",
        r"\b(phpinfo|passthru|shell_exec|proc_open)\b",
    ],
    "base64_or_datauri": [
        r"(?:[A-Za-z0-9+/]{4}){6,}={0,2}",  # base64-ish (long)
        r"data:\w+\/[\w+-]+;base64,",
    ],
    "hex_binary": [
        r"(?:0x[0-9a-fA-F]{2,}){10,}",  # molte hex
        r"(?:\\x[0-9a-fA-F]{2}){10,}",  # \xNN sequences
    ],
    "suspicious_shell": [
        r"\b(nc|netcat|wget|curl|bash|sh|chmod|chown|sudo|su|rm\s+-rf)\b",
        r"[;&\|]{1,}",  # ; & | pipe characters used in shell injection
    ],
    "urls": [
        r"https?:\/\/",  # presenza URL
        r"file:\/\/\/",  # file URIs
    ],
}

# Flattened patterns for iteration
FLATTENED = [(k, re.compile(p, re.IGNORECASE | re.DOTALL)) for k, ps in PATTERNS.items() for p in ps]


# --- Helpers ---
def normalize_text(text: str) -> str:
    """Normalizzazione base + rimozione di alcuni invisibili."""
    # NFKC per compatibilità (unisci confusable characters)
    text = unicodedata.normalize("NFKC", text)
    # Rimuovi caratteri invisibili usati spesso per evade detection
    for ch in ("\u200b", "\u200c", "\u200d", "\ufeff"):
        text = text.replace(ch, "")
    # Escapa l'HTML solo per sicurezza se poi verrà renderizzato
    text = html.escape(text)
    return text.strip()


def score_matches(text: str) -> Dict[str, int]:
    """Conta quante volte matcha ogni categoria di pattern."""
    counts: Dict[str, int] = {}
    for name, pattern in FLATTENED:
        m = pattern.search(text)
        if m:
            counts[name] = counts.get(name, 0) + 1
    return counts


def long_non_alpha_sequence(text: str, threshold: int = 50) -> bool:
    """
    Rileva sequenze molto lunghe senza spazi (es. base64 o blob).
    threshold = lunghezza minima per considerare sospetto.
    """
    for token in re.findall(r"\S{"+str(threshold)+r",}", text):
        # se il token contiene molti simboli o numeri -> sospetto
        non_alpha_ratio = sum(1 for c in token if not c.isalpha()) / max(1, len(token))
        if non_alpha_ratio > 0.4:
            return True
    return False


def sanitize_user_prompt(user_input: str) -> str:
    """
    Sanifica il prompt utente e restituisce una stringa sicura.

    - Se sicuro: ritorna il testo normalizzato pronto all'uso.
    - Se warn o block: ritorna un messaggio di blocco e non permette codice pericoloso.
    """

    normalized = normalize_text(user_input)
    reasons = []
    score = 0.0

    # lunghezza
    if len(normalized) > MAX_LENGTH:
        reasons.append("too_long")
        score += 0.5

    # pattern matching
    matches = score_matches(normalized)
    print("DEBUG MATCHES:", matches)  # per debug
    for category, count in matches.items():
        weight = 0.15
        if category == "script_html":
            weight = 0.25
        if category == "base64_or_datauri":
            weight = 0.2
        if category == "code_exec":
            weight = 0.25
        score += weight * count
        reasons.append(category)

    # sequenze non-alpha lunghe
    if long_non_alpha_sequence(normalized, threshold=60):
        reasons.append("long_non_alpha_sequence")
        score += 0.2

    # simboli shell
    if re.search(r"[<>]{2,}", normalized) or re.search(r"(?:\|\||\&\&|\;){2,}", normalized):
        reasons.append("shell_symbols")
        score += 0.1

    # URL / file / data URI
    if re.search(r"file:\/\/\/|data:\w+\/", normalized, flags=re.IGNORECASE):
        reasons.append("file_data_uri")
        score += 0.15

    score = min(1.0, score)

    # verdetto: ora blocca anche i warning
    if score >= MEDIUM_RISK_THRESHOLD:
        # Blocca sempre se c'è match di warning o alto rischio
        return f"error"

    # altrimenti ritorna il testo normale
    return normalized

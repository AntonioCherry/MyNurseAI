import re
import math
import io
import subprocess
from PyPDF2 import PdfReader
from statistics import mean

def classify_with_ollama(text: str) -> tuple[bool, str, float]:
    """
    Usa Ollama (modello Mistral) per determinare se il testo è medico o non medico.
    Restituisce (is_medical, label, confidence)
    """
    prompt = f"""
Sei un classificatore testuale.
Determina se il seguente testo appartiene al dominio medico-sanitario.
Rispondi esclusivamente con una parola: "medico" o "non medico".

Testo:
{text[:2000]}
    """

    try:
        result = subprocess.run(
            ["ollama", "run", "mistral"],
            input=prompt.encode("utf-8"),
            capture_output=True,
            timeout=60
        )

        if result.returncode != 0:
            raise RuntimeError(result.stderr.decode())

        raw_output = result.stdout.decode().strip().lower()

        # Analizza risposta
        if "medico" in raw_output and "non" not in raw_output:
            return True, "medico", 0.9
        elif "non medico" in raw_output or "non-medico" in raw_output:
            return False, "non medico", 0.9
        else:
            return False, raw_output, 0.5

    except Exception as e:
        return False, f"Errore Ollama: {e}", 0.0


def shannon_entropy(s: str) -> float:
    """Calcola entropia per identificare testo codificato o nascosto."""
    prob = [float(s.count(c)) / len(s) for c in dict.fromkeys(s)]
    return -sum(p * math.log(p, 2) for p in prob)


def check_pdf_structure(pdf_bytes: bytes) -> tuple[bool, str]:
    """Controlla che il PDF non contenga oggetti sospetti."""
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        for page in reader.pages:
            raw = page.extract_text() or ""
            if re.search(r"(?i)(<script|javascript:|eval\(|base64,|import )", raw):
                return False, "Trovato contenuto sospetto o codice embedded nel PDF."
        return True, ""
    except Exception as e:
        return False, f"Errore nella lettura del PDF: {e}"


def validate_pdf_content(pdf_bytes: bytes) -> tuple[bool, str]:
    errors = []
    suspicion_score = 0.0  # accumula evidenze
    SCORE_THRESHOLD = 1.0  # soglia combinata per rifiutare (tuneable)

    # --- estrai testo grezzo ---
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages_texts = [page.extract_text() or "" for page in reader.pages]
    text = "\n".join(pages_texts)

    # --- controllo base sulla lunghezza ---
    if len(text.strip()) < 300:
        errors.append("Documento troppo breve o privo di testo leggibile.")
        suspicion_score += 0.8

    # --- controllo struttura ---
    struct_ok, struct_msg = check_pdf_structure(pdf_bytes)
    if not struct_ok:
        errors.append(struct_msg)
        suspicion_score += 0.8

    # --- normalizzazione per pattern detection robusta ---
    # 1) versione compatta: rimuove spazi/newline e caratteri invisibili per catturare obfuscation semplice
    compact = re.sub(r"\s+", "", text)  # rimuove tutti gli spazi e newlines
    compact_lower = compact.lower()

    # 2) versione "alphanum-only" per cercare sequenze base64 o codici lunghi
    alnum = re.sub(r"[^A-Za-z0-9+/=]", "", text)

    # --- pattern Base64 anche spezzato su più linee ---
    # cerca sequenze di 50+ caratteri alfanumerici tipiche di base64
    if re.search(r"[A-Za-z0-9+/=]{50,}", alnum):
        errors.append("Pattern compatibile con Base64 o testo codificato rilevato.")
        suspicion_score += 1.0

    # --- entropia: sia globale sia per chunk ---
    try:
        chunks = [text[i:i+200] for i in range(0, len(text), 200)]
        entropy_vals = [shannon_entropy(c) for c in chunks if len(c) > 50]
        avg_entropy = mean(entropy_vals) if entropy_vals else 0
        entropy_total = shannon_entropy(re.sub(r"\s+", "", text)) if text.strip() else 0
    except Exception:
        avg_entropy = 0
        entropy_total = 0

    # se l'entropia globale o media è alta -> sospetto
    if avg_entropy > 5.3 or entropy_total > 5.3:
        errors.append("Entropia elevata: possibile testo codificato o anomalo.")
        suspicion_score += 1.0

    # --- ricerca frammenti di codice / simboli tipici ---
    # se molte righe contengono caratteri tipici di codice, aumentiamo il sospetto
    code_like_lines = 0
    for line in text.splitlines():
        # conteggio di simboli come {},;,(),=,<>,import,def,class,printf
        if re.search(r"[{}<>;=()/\\]|import\s|\bdef\b|\bclass\b|\bprintf\b", line):
            code_like_lines += 1
    if code_like_lines > 2:
        errors.append(f"Rilevate {code_like_lines} righe con pattern simili a codice.")
        suspicion_score += 0.8

    # --- ricerca parole chiave "DAN", "jailbreak", "ignore previous", "act as" anche se spezzate ---
    # per essere robusti, cerchiamo le parole chiave sia in forma normale che nella versione compatta (senza spazi)
    keywords = [
        "ignorepreviousinstructions", "ignoreprevious", "ignoreinstructions",
        "youarenow", "actas", "jailbreak", "dan", "systemprompt",
        "openaiapikey", "openai.api_key", "openai key", "grantaccess"
    ]
    found_keywords = []
    low_text = text.lower()
    for kw in keywords:
        if kw in re.sub(r"\W+", "", low_text):  # versione completamente alfanumerica
            found_keywords.append(kw)
    # verifica anche nella versione compact (rimuove solo spazi)
    for kw in keywords:
        if kw in compact_lower:
            if kw not in found_keywords:
                found_keywords.append(kw)

    if found_keywords:
        errors.append(f"Parole chiave potenzialmente malevole rilevate: {', '.join(found_keywords)}")
        suspicion_score += 1.2

    # --- Controlli LLM (pertinenza semantica e rilevamento di istruzioni) ---
    # Esegui il controllo semantico solo se non siamo già fortemente sospettosi (per risparmiare risorse)
    if suspicion_score < 2.0:
        valid, label, conf = classify_with_ollama(text)
        if not valid:
            errors.append("Il documento non appare medico (classificazione LLM).")
            suspicion_score += 0.6
    else:
        # se già molto sospettoso, possiamo comunque chiamare LLM in modalità "detection" opzionale
        try:
            valid, label, conf = classify_with_ollama(text)
            if not valid:
                errors.append("Il documento non appare medico (classificazione LLM).")
                suspicion_score += 0.6
        except Exception:
            # non blocchiamo per errore LLM, ma segnaliamo
            errors.append("Errore durante la classification LLM (verificare log).")

    # --- final decision ---
    if suspicion_score >= SCORE_THRESHOLD or errors:
        # azione consigliata: non indicizzare, mettere in quarantine e notificare un admin
        return False, "; ".join(errors) if errors else "Documento sospetto."

    return True, ""
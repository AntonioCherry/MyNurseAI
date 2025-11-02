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
    if not s:
        return 0.0
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
    """
    Analizza il contenuto del PDF per individuare testo sospetto o codificato.
    Migliorata per ridurre falsi positivi su documenti medici.
    """
    def alpha_ratio(s: str) -> float:
        """Percentuale di lettere in una stringa."""
        if not s:
            return 0.0
        letters = len(re.findall(r"[A-Za-z]", s))
        return letters / max(1, len(s))

    errors = []
    suspicion_score = 0.0
    SCORE_THRESHOLD = 2.2  # soglia più alta per ridurre falsi positivi

    # --- estrai testo grezzo ---
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages_texts = [page.extract_text() or "" for page in reader.pages]
    text = "\n".join(pages_texts)
    low_text = text.lower()

    # --- controllo base sulla lunghezza ---
    if len(text.strip()) < 300:
        errors.append("Documento troppo breve o privo di testo leggibile.")
        suspicion_score += 0.6

    # --- controllo struttura ---
    struct_ok, struct_msg = check_pdf_structure(pdf_bytes)
    if not struct_ok:
        errors.append(struct_msg)
        suspicion_score += 0.9

    # --- normalizzazione ---
    compact = re.sub(r"\s+", "", text)
    compact_lower = compact.lower()
    alnum = re.sub(r"[^A-Za-z0-9+/=]", "", text)

    # --- rilevamento Base64 (più restrittivo) ---
    base64_matches = list(re.finditer(r"(?:[A-Za-z0-9+/]{80,}={0,2})", alnum))
    base64_flag = False
    for m in base64_matches:
        chunk = m.group(0)
        if shannon_entropy(chunk) > 4.5:
            base64_flag = True
            break
    if base64_flag:
        errors.append("Pattern compatibile con Base64 o testo codificato rilevato.")
        suspicion_score += 1.0

    # --- entropia ---
    try:
        chunks = [text[i:i+200] for i in range(0, len(text), 200)]
        entropy_vals = [shannon_entropy(c) for c in chunks if len(c) > 50]
        avg_entropy = mean(entropy_vals) if entropy_vals else 0
        entropy_total = shannon_entropy(re.sub(r"\s+", "", text)) if text.strip() else 0
    except Exception:
        avg_entropy = entropy_total = 0

    if avg_entropy > 5.5 or entropy_total > 5.5:
        errors.append("Entropia elevata: possibile testo codificato o anomalo.")
        suspicion_score += 1.0

    # --- rilevamento linee di codice (versione migliorata) ---
    code_like_lines = 0
    for line in text.splitlines():
        line_stripped = line.strip()

        # ignora linee corte o quasi vuote
        if len(line_stripped) < 10:
            continue

        # ignora linee con densità alfabetica troppo bassa (probabile numero o tabella)
        if alpha_ratio(line_stripped) < 0.35:
            continue

        # ignora linee tipiche dei referti (es. valori, unità di misura)
        if re.search(
                r"\b(g\/dl|mmol\/l|mg\/dl|u\/l|creatinina|emoglobina|globuli|bilirubina|sodio|potassio|esame|referto|diagnosi)\b",
                line_stripped, re.IGNORECASE):
            continue

        # considera "code-like" solo se contiene più pattern di codice insieme
        symbol_count = len(re.findall(r"[{}<>;=()/\\]", line_stripped))
        keyword_hits = len(re.findall(r"\b(import|def|class|printf|var|function)\b", line_stripped, re.IGNORECASE))

        if symbol_count >= 3 or keyword_hits >= 1:
            code_like_lines += 1

    # aumenta la soglia per ridurre falsi positivi (ora serve molto codice per triggerare)
    if code_like_lines > 15:
        errors.append(f"Rilevate {code_like_lines} righe con pattern simili a codice.")
        suspicion_score += 0.5

    # --- ricerca parole chiave malevole (token-based) ---
    clean_for_tokens = re.sub(r"[^a-z0-9\s]", " ", low_text)
    tokens = clean_for_tokens.split()
    keywords = {
        "ignorepreviousinstructions", "ignoreprevious", "ignoreinstructions",
        "youarenow", "actas", "jailbreak", "dan", "systemprompt",
        "openaiapikey", "openai.api_key", "openai", "grantaccess"
    }
    found_keywords = [kw for kw in keywords if kw in tokens]

    for kw in keywords:
        if re.search(r"\b" + re.escape(kw) + r"\b", compact_lower):
            if kw not in found_keywords:
                found_keywords.append(kw)

    if found_keywords:
        errors.append(f"Parole chiave potenzialmente malevole rilevate: {', '.join(found_keywords)}")
        suspicion_score += 1.2

    # --- controllo LLM ---
    if suspicion_score < 1.6:
        valid, label, conf = classify_with_ollama(text)
        if not valid:
            errors.append("Il documento non appare medico (classificazione LLM).")
            suspicion_score += 0.6
    else:
        try:
            valid, label, conf = classify_with_ollama(text)
            if not valid:
                errors.append("Il documento non appare medico (classificazione LLM).")
                suspicion_score += 0.4
        except Exception:
            errors.append("Errore durante la classification LLM (verificare log).")

    # --- decisione finale ---
    if suspicion_score >= SCORE_THRESHOLD or errors:
        return False, "; ".join(errors) if errors else "Documento sospetto."
    return True, ""

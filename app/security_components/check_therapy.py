from ollama import chat, ChatResponse

def is_therapy_related(text: str) -> bool:
    """
    Usa Mistral (via Ollama) in modalità few-shot per determinare
    se un testo riguarda una terapia o meno.
    Restituisce True/False.
    """
    few_shot_prompt = f"""
Sei un assistente clinico. Devi stabilire se il testo fornito
contiene riferimenti a TERAPIE, TRATTAMENTI o FARMACI.

Classifica ogni testo come:
- "TERAPIA" se contiene riferimenti a cure, farmaci, dosaggi, prescrizioni o trattamenti.
- "NON_TERAPIA" se parla solo di diagnosi, sintomi, controlli o referti generici.

Esempi:
1. "Il paziente assume amoxicillina 500mg ogni 8 ore." → TERAPIA
2. "Diagnosi di bronchite acuta, follow-up tra 7 giorni." → NON_TERAPIA
3. "Ha sospeso la cura antibiotica per effetti collaterali." → TERAPIA
4. "Il paziente lamenta tosse persistente, in attesa di referto." → NON_TERAPIA
5. "Terapia fisica riabilitativa 3 volte a settimana." → TERAPIA

Ora classifica il seguente testo:
"{text}"

Rispondi SOLO con "TERAPIA" o "NON_TERAPIA".
    """

    response: ChatResponse = chat(
        model="mistral",
        messages=[{"role": "user", "content": few_shot_prompt}],
        stream=False
    )

    output = response.message.content.strip().lower()
    return "terapia" in output and "non" not in output

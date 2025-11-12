def verify_response_with_llm(response, retrieved_texts, chatbot):
    """
    Controlla se la risposta del chatbot è supportata dai documenti.
    - response: testo generato dal chatbot
    - retrieved_texts: lista di documenti recuperati
    - chatbot: istanza di OllamaWrapper o altro LLM
    Restituisce:
    - is_supported: True se tutta la risposta è supportata
    - feedback: testo da mostrare all'utente
    """
    # Costruzione del prompt di fact-check
    context = "\n\n".join(retrieved_texts) if retrieved_texts else "(Nessun documento disponibile)"

    fact_check_prompt = f"""
Sei un verificatore automatico. 
Analizza la risposta fornita e verifica se tutte le informazioni riportate sono presenti nel contesto.
Contesto:
{context}

Risposta generata:
{response}

Istruzioni:
- Restituisci solo le frasi o segmenti della risposta NON presenti nel contesto.
- Se tutta la risposta è supportata, scrivi "TUTTO SUPPORTATO".
"""

    verification_result = chatbot(fact_check_prompt)[0]["generated_text"]
    print("ciao")
    if "TUTTO SUPPORTATO" in verification_result.upper():
        return True, "TUTTO SUPPORTATO"
    else:
        feedback = (
            "⚠️ Alcune parti della risposta potrebbero non essere supportate dai documenti\n"
        )
        return False, feedback

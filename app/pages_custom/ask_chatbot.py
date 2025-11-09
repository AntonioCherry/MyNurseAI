import streamlit as st
import os, difflib
from ollama import chat, ChatResponse
from langchain.vectorstores import Chroma
from langchain.embeddings import HuggingFaceEmbeddings
from sqlalchemy.orm import Session
from app.components.sidebar import sidebar
from app.models.user import User
from app.security_components.check_therapy import is_therapy_related
from app.security_components.PII_obfuscation import obscure_pii


# --- Wrapper Ollama ---
# --- Utilizzato per impacchettare le richieste indirizzate ad ollama ---
class OllamaWrapper:
    def __init__(self, model_name):
        self.model_name = model_name

    def __call__(self, prompt):
        response: ChatResponse = chat(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            stream=False
        )
        return [{"generated_text": response.message.content}]

# --- Caricamento dell'LLM ---
@st.cache_resource
def load_model():
    return OllamaWrapper(model_name="mistral")

# --- Funzione che sulla base dell'email dell'utente reperisce tutte le info in formato vettoriale
# --- dalla rispetiva cartella di chromaDB
def load_vectorstore(email_paziente):
    persist_dir = os.path.join("chroma_db", email_paziente)
    if not os.path.exists(persist_dir):
        return None
    embeddings = HuggingFaceEmbeddings(
        model_name="intfloat/multilingual-e5-large",
        encode_kwargs={"normalize_embeddings": True}
    )
    vectorstore = Chroma(
        persist_directory=persist_dir,
        embedding_function=embeddings,
        collection_name="docs"
    )
    return vectorstore


# --- Funzione che restituisce tutti i pazienti di un determinato medico ---
def get_pazienti_del_medico(email_medico: str, db: Session):
    return db.query(User).filter(User.medicoAssociato == email_medico).all()


def build_rag_prompt(query, retrieved_docs, paziente_nome=None, contains_therapy: bool = False):
    """
    Costruisce il prompt RAG.
    - query: testo della domanda
    - retrieved_docs: lista di stringhe recuperate dal retriever
    - paziente_nome: (opzionale) nome del paziente per contesto
    - contains_therapy: True se il contesto contiene informazioni terapeutiche
    """
    context = "\n\n".join(retrieved_docs) if retrieved_docs else "(Nessun documento rilevante trovato.)"
    patient_info = f"\nIl paziente in questione è {paziente_nome}." if paziente_nome else ""

    # Istruzione specifica riguardo la terapia: vincola il modello a non inventare terapie,
    # ma a rispondere solo sulla base delle terapie prescritte dal medico a cui quel paziente fa riferimento.
    if contains_therapy:
        therapy_instruction = (
            "Nei documenti forniti ci sono informazioni su terapie o trattamenti. "
            "Se rispondi citando una terapia, riporta esclusivamente quanto presente nei documenti "
            "e indica chiaramente la fonte o il referto da cui proviene l'informazione."
        )
    else:
        therapy_instruction = (
            "ATTENZIONE: nei documenti forniti non risultano informazioni su terapie o farmaci. "
            "Non proporre né inventare terapie, farmaci, dosaggi o prescrizioni. "
            "Limita la risposta a informazioni diagnostiche, descrittive o di follow-up presenti nel contesto."
        )

    prompt = f"""
Sei un infermiere virtuale che assiste un medico. Rispondi in modo chiaro, professionale e conservativo.
{patient_info}

{therapy_instruction}

Contesto (da usare esclusivamente per rispondere; non aggiungere informazioni esterne):
{context}

Domanda del medico/paziente:
{query}

Istruzioni di formato:
- Rispondi solo con informazioni presenti nel contesto.
- Se non trovi informazioni pertinenti, rispondi esplicitando che nei documenti non sono presenti dati utili.
- Non includere consigli farmacologici o terapie se non esplicitamente presenti nei documenti.
- Se citi parti dei documenti, indica brevemente la loro fonte (es. "Da referto del DD/MM/YYYY").

Risposta:
"""
    return prompt

def identify_paziente_in_query(query, pazienti):
    """
    Cerca di capire da una domanda a quale paziente si riferisce il medico.
    Restituisce l'oggetto Paziente più simile o None se non riconosciuto.
    """
    query_lower = query.lower()
    nomi_possibili = {f"{p.nome.lower()} {p.cognome.lower()}": p for p in pazienti}

    # Cerca match esatto
    for full_name, paziente in nomi_possibili.items():
        if full_name in query_lower:
            return paziente

    # Se non c'è match esatto, prova fuzzy matching
    match = difflib.get_close_matches(query_lower, nomi_possibili.keys(), n=1, cutoff=0.6)
    if match:
        return nomi_possibili[match[0]]
    return None


def ask_chatbot(db,user):
    sidebar(user)

    st.title("💬 Chat con il tuo infermiere virtuale")

    chatbot = load_model()

    # Se medico, carica tutti i suoi pazienti
    if user.role == "Medico":
        pazienti = get_pazienti_del_medico(user.email, db)
    else:
        pazienti = [user]

    # Memoria chat
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    for role, msg in st.session_state.chat_history:
        if role == "user":
            st.markdown(f"🧑‍⚕️ **Tu:** {msg}")
        else:
            st.markdown(f"🤖 **MyNurseAI:** {msg}")

    user_input = st.text_input("Scrivi la tua domanda:", value="", key="chat_input")

    if st.button("💬 Invia"):
        if not user_input.strip():
            st.warning("⚠️ Inserisci un messaggio prima di inviare.")
            return

        st.session_state.chat_history.append(("user", user_input))

        with st.spinner("L'infermiere sta cercando nei documenti..."):
            response = None

            # --- Se medico ---
            if user.role == "Medico":
                #1. Cerca di identificare il paziente nella query al chatbot.
                selected_paziente = identify_paziente_in_query(user_input, pazienti)
                #1.1. Se  non trova nessun riferimento a pazienti di quel medico allora restituisce errore.
                if not selected_paziente:
                    response = (
                        "Non ho trovato riferimenti chiari a un paziente tra i tuoi assistiti. "
                        "Puoi ripetere la domanda specificando il nome completo del paziente?"
                    )
                else:
                    #2. Tramite l'email del paziente viene caricato il vector store di quel paziente specifico.
                    paziente_email = selected_paziente.email
                    vectorstore = load_vectorstore(paziente_email)
                    if vectorstore is None:
                        response = (
                            f"Non ho trovato documenti clinici per "
                            f"{selected_paziente.nome} {selected_paziente.cognome}."
                        )
                    else:
                        #3. Vengono estratti dal vector store di quel paziente i k=3 documenti più pertinenti
                        #   I documenti poi verranno utilizzati per costruire il contesto su cui si baserà
                        #   il chatbot per generare una risposta.
                        retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
                        docs = retriever.get_relevant_documents(user_input)
                        retrieved_texts = [d.page_content for d in docs]
                        context = "\n\n".join(retrieved_texts)

                        # --- Controllo terapeutico ---
                        contains_therapy = is_therapy_related(context)
                        #4. Costruzione del prompt sulla base del contesto recuperato dal vector store.
                        rag_prompt = build_rag_prompt(
                            user_input,
                            retrieved_texts,
                            paziente_nome=f"{selected_paziente.nome} {selected_paziente.cognome}",
                            contains_therapy= contains_therapy
                        )
                        #5. Chiamata al chatbot e restituzione risposta
                        raw_response = chatbot(rag_prompt)[0]["generated_text"]
                        response = obscure_pii(raw_response)

                        #6. --- Controllo se l'input dell'utente riguarda una terapia ---
                        query_is_therapy = is_therapy_related(user_input)

                        #7. Se nella query utente è presente un riferimento a terapie o farmaci e
                        #   nel contesto recuperato non ci sono riferimenti a tali terapie e farmaci allora da errore
                        if query_is_therapy and not contains_therapy:
                            response = (
                                "⚠️ Nei documenti consultati non sono presenti indicazioni terapeutiche. "
                                "Posso riportare solo informazioni cliniche generali relative al caso, "
                                "ma non dettagli su trattamenti o farmaci."
                            )


            # --- Se paziente ---
            else:
                paziente_email = user.email
                vectorstore = load_vectorstore(paziente_email)
                if vectorstore is None:
                    response = "Non ho trovato informazioni nei tuoi documenti."
                else:
                    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
                    docs = retriever.get_relevant_documents(user_input)
                    retrieved_texts = [d.page_content for d in docs]
                    context = "\n\n".join(retrieved_texts)


                    contains_therapy = is_therapy_related(context)

                    if not retrieved_texts:
                        response = (
                            "Non ho trovato informazioni utili nei tuoi documenti "
                            "per rispondere alla domanda."
                        )
                    else:
                        rag_prompt = build_rag_prompt(
                            user_input,
                            retrieved_texts,
                            contains_therapy=contains_therapy
                        )
                        response = chatbot(rag_prompt)[0]["generated_text"]

                        query_is_therapy = is_therapy_related(user_input)

                        # --- Logica più intelligente: ---
                        #  - Se la domanda riguarda una terapia
                        #  - ma nei documenti non ci sono riferimenti terapeutici
                        #  -> Mostra messaggio di avviso
                        if query_is_therapy and not contains_therapy:
                            response = (
                                "⚠️ Nei documenti consultati non sono presenti indicazioni terapeutiche. "
                                "Posso riportare solo informazioni cliniche generali relative al caso, "
                                "ma non dettagli su trattamenti o farmaci."
                            )

        st.session_state.chat_history.append(("bot", response))
        st.rerun()

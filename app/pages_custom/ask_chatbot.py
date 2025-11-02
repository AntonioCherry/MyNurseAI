import streamlit as st
import os, difflib
from ollama import chat, ChatResponse
from langchain.vectorstores import Chroma
from langchain.embeddings import HuggingFaceEmbeddings
from sqlalchemy.orm import Session
from app.components.sidebar import sidebar
from app.models.user import User

# --- Wrapper Ollama ---
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


@st.cache_resource
def load_model():
    return OllamaWrapper(model_name="qwen3:1.7b")


def load_vectorstore(email_paziente):
    persist_dir = os.path.join("chroma_db", email_paziente)
    if not os.path.exists(persist_dir):
        return None
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vectorstore = Chroma(
        persist_directory=persist_dir,
        embedding_function=embeddings,
        collection_name="docs"
    )
    return vectorstore



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

    # Istruzione specifica riguardo la terapia: vincola il modello a non inventare terapie
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
        pazienti = [user]  # se paziente loggato

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
                selected_paziente = identify_paziente_in_query(user_input, pazienti)

                if not selected_paziente:
                    response = (
                        "Non ho trovato riferimenti chiari a un paziente tra i tuoi assistiti. "
                        "Puoi ripetere la domanda specificando il nome completo del paziente?"
                    )
                else:
                    paziente_email = selected_paziente.email
                    vectorstore = load_vectorstore(paziente_email)
                    if vectorstore is None:
                        response = (
                            f"Non ho trovato documenti clinici per "
                            f"{selected_paziente.nome} {selected_paziente.cognome}."
                        )
                    else:
                        retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
                        docs = retriever.get_relevant_documents(user_input)
                        retrieved_texts = [d.page_content for d in docs]
                        context = "\n\n".join(retrieved_texts)

                        # --- Controllo terapeutico ---
                        keywords_therapy = [
                            "terapia", "trattamento", "cura", "farmaco",
                            "posologia", "assumere", "prescrizione",
                            "somministrazione", "protocollo terapeutico"
                        ]
                        contains_therapy = any(kw in context.lower() for kw in keywords_therapy)

                        rag_prompt = build_rag_prompt(
                            user_input,
                            retrieved_texts,
                            paziente_nome=f"{selected_paziente.nome} {selected_paziente.cognome}",
                            contains_therapy= contains_therapy
                        )

                        response = chatbot(rag_prompt)[0]["generated_text"]

                        # --- Controllo post-risposta ---
                        therapy_words = ["assum", "farmaco", "terapia", "trattamento", "cura", "mg", "somministr"]
                        if not contains_therapy and any(w in response.lower() for w in therapy_words):
                            response = (
                                "⚠️ Nei documenti consultati non sono presenti indicazioni terapeutiche. "
                                "Riporto solo le informazioni cliniche disponibili relative al caso."
                            )

            # --- Se paziente ---
            else:
                paziente_email = user.email
                vectorstore = load_vectorstore(paziente_email)
                if vectorstore is None:
                    response = "Non ho trovato informazioni nei tuoi documenti."
                else:
                    retriever = vectorstore.as_retriever(search_kwargs={"k": 1})
                    docs = retriever.get_relevant_documents(user_input)
                    retrieved_texts = [d.page_content for d in docs]
                    context = "\n\n".join(retrieved_texts)

                    # --- Controllo terapeutico anche per pazienti ---
                    keywords_therapy = [
                        "terapia", "trattamento", "cura", "farmaco",
                        "posologia", "assumere", "prescrizione",
                        "somministrazione", "protocollo terapeutico"
                    ]
                    contains_therapy = any(kw in context.lower() for kw in keywords_therapy)

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

                        # --- Controllo post-risposta ---
                        therapy_words = ["assum", "farmaco", "terapia", "trattamento", "cura", "mg", "somministr"]
                        if not contains_therapy and any(w in response.lower() for w in therapy_words):
                            response = (
                                "⚠️ Nei documenti consultati non sono presenti indicazioni terapeutiche. "
                                "Non posso fornirti indicazioni terapeutiche se non sono state prima indicate dal tuo medico curante!"
                            )

        st.session_state.chat_history.append(("bot", response))
        st.rerun()

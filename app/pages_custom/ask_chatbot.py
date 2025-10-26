import streamlit as st
import os, difflib, time
from ollama import chat, ChatResponse
from langchain.vectorstores import Chroma
from langchain.embeddings import HuggingFaceEmbeddings
from sqlalchemy.orm import Session
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


def build_rag_prompt(query, retrieved_docs, paziente_nome=None):
    context = "\n\n".join(retrieved_docs)
    patient_info = f"\nIl paziente in questione è {paziente_nome}." if paziente_nome else ""
    prompt = f"""
Sei un infermiere virtuale che assiste un medico.
Analizza i documenti clinici disponibili e rispondi in linguaggio chiaro e professionale.{patient_info}

Contesto:
{context}

Domanda del medico:
{query}

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
    css_path = os.path.join("app", "page_styles", "sidebar.css")
    if os.path.exists(css_path):
        with open(css_path) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

        # --- SIDEBAR ---
        with st.sidebar:
            st.markdown(f"""
                <div class="profile-container">
                    <img src="https://cdn-icons-png.flaticon.com/512/847/847969.png" alt="Profilo">
                    <h3>👋 Ciao, {user.nome}!</h3>
                </div>
            """, unsafe_allow_html=True)

            st.markdown('<div class="sidebar-sep"></div>', unsafe_allow_html=True)

            if user.role == "Medico":
                # --- Tutti i bottoni della sidebar uguali nello stile ---
                sidebar_items = [
                    ("🏠 Area Personale", "area_personale"),
                    ("🧍‍♂️ Visualizza Pazienti", "show_pazienti"),
                    ("💬 Chatbot", "ask_chatbot")
                ]
            elif user.role == "Paziente":
                # --- Tutti i bottoni della sidebar uguali nello stile ---
                sidebar_items = [
                    ("🏠 Area Personale", "area_personale"),
                    ("🧍‍♂️ Visualizza Documenti", "show_docs"),
                    ("💬 Chatbot", "ask_chatbot")
                ]

            for label, page in sidebar_items:
                if st.button(label, key=f"btn_{page}", use_container_width=True):
                    st.session_state.current_page = page
                    st.rerun()

            st.markdown('<div class="sidebar-sep"></div>', unsafe_allow_html=True)
            if st.button("🚪 Logout", use_container_width=True):
                st.session_state.logged_in = False
                st.session_state.user = None
                st.session_state.show_register = False
                st.query_params.clear()
                st.success("Logout effettuato con successo!")
                time.sleep(1)
                st.rerun()

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
                        rag_prompt = build_rag_prompt(
                            user_input,
                            retrieved_texts,
                            paziente_nome=f"{selected_paziente.nome} {selected_paziente.cognome}"
                        )
                        response = chatbot(rag_prompt)[0]["generated_text"]

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

                    if not retrieved_texts:
                        response = (
                            "Non ho trovato informazioni utili nei tuoi documenti "
                            "per rispondere alla domanda."
                        )
                    else:
                        rag_prompt = build_rag_prompt(user_input, retrieved_texts)
                        response = chatbot(rag_prompt)[0]["generated_text"]

        st.session_state.chat_history.append(("bot", response))
        st.rerun()

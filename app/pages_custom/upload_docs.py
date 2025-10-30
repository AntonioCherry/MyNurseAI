import streamlit as st
import time
import io
import os
from PyPDF2 import PdfReader
from app.models.doc import Doc
from langchain.text_splitter import CharacterTextSplitter
from langchain.vectorstores import Chroma
from langchain.embeddings import HuggingFaceEmbeddings
from app.utils.pdf_validation import validate_pdf_content

def upload_docs(db, user):
    # Percorso del file CSS
    css_path = os.path.join("app", "page_styles", "sidebar.css")

    # Carica il contenuto e applica lo stile
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

    # --- Controllo paziente selezionato ---
    if "selected_paziente" not in st.session_state or st.session_state.selected_paziente is None:
        st.warning("⚠️ Nessun paziente selezionato")
        return

    p = st.session_state.selected_paziente
    st.title(f"📄 Documenti di {p.nome} {p.cognome}")

    # --- Flag upload per paziente ---
    patient_flag_key = f"file_uploaded_{p.email}"
    if patient_flag_key not in st.session_state:
        st.session_state[patient_flag_key] = False

    # --- Cartella paziente per ChromaDB ---
    persist_dir = os.path.join("chroma_db", p.email)
    os.makedirs(persist_dir, exist_ok=True)

    # --- Carica o crea vectorstore ---
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vectorstore = Chroma(persist_directory=persist_dir, embedding_function=embeddings, collection_name="docs")

    # --- Upload PDF (sezione modificata) ---
    uploaded_file = st.file_uploader("Carica un nuovo documento", type=["pdf"])
    if uploaded_file is not None:
        processing_key = f"upload_processing_{p.email}"
        # inizializza la chiave di lock
        if processing_key not in st.session_state:
            st.session_state[processing_key] = False

        # evita doppio submit
        if st.session_state[processing_key]:
            st.info("Elaborazione in corso, attendere...")
        else:
            # imposta lock
            st.session_state[processing_key] = True
            try:
                file_bytes = uploaded_file.read()

                # --- VALIDAZIONE PDF (usa la tua validate_pdf_content) ---
                valid, message = validate_pdf_content(file_bytes)
                if not valid:
                    st.error(f"❌ Upload rifiutato: {message}")
                    # rimuovi il lock e non impostare flag permanente
                    st.session_state[processing_key] = False
                else:
                    # 1️⃣ Salva su PostgreSQL
                    new_doc = Doc(
                        filename=uploaded_file.name,
                        paziente_email=p.email,
                        file_data=file_bytes
                    )
                    db.add(new_doc)
                    db.commit()
                    st.success(f"Documento '{uploaded_file.name}' caricato con successo!")

                    # 2️⃣ Salva su ChromaDB
                    try:
                        reader = PdfReader(io.BytesIO(file_bytes))
                        text = "".join([page.extract_text() or "" for page in reader.pages])

                        text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
                        chunks = text_splitter.split_text(text)

                        vectorstore.add_texts(chunks)
                        vectorstore.persist()
                        st.success(f"Documento '{uploaded_file.name}' indicizzato su ChromaDB!")
                    except Exception as e:
                        st.error(f"Errore durante il salvataggio su ChromaDB: {e}")
                    finally:
                        # rimuovi il lock
                        st.session_state[processing_key] = False

            except Exception as e:
                st.error(f"Errore durante l'upload: {e}")
                st.session_state[processing_key] = False

    # --- Lista documenti ---
    docs = db.query(Doc).filter(Doc.paziente_email == p.email).all()
    if not docs:
        st.info("Non ci sono documenti caricati per questo paziente.")
        return

    st.markdown("### Documenti caricati:")

    for d in docs:
        cols = st.columns([3, 1])
        with cols[0]:
            st.markdown(f"**{d.filename}**")
        with cols[1]:
            st.download_button(
                label="📥 Scarica",
                data=d.file_data,
                file_name=d.filename,
                mime="application/pdf",
                key=f"download_{d.id}"
            )
        st.markdown("<div style='margin:2px 0;border-bottom:1px solid #ddd;'></div>", unsafe_allow_html=True)


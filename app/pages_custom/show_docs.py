import streamlit as st
import time
import io
import os
from PyPDF2 import PdfReader
from app.models.doc import Doc
from langchain.text_splitter import CharacterTextSplitter
from langchain.vectorstores import Chroma
from langchain.embeddings import HuggingFaceEmbeddings

def show_docs(db, user):
    st.markdown("""
        <style>
        [data-testid="stSidebar"] {
            background-color: #ffffff;
            color: #333;
            font-family: 'Arial', sans-serif;
            padding-top: 20px;
            border-right: 2px solid #ddd;
        }
        .sidebar-link {
            display: block;
            width: 100%;
            padding: 12px 16px;
            border-radius: 8px;
            text-decoration: none !important;
            color: #333 !important;
            background-color: transparent;
            transition: background-color 0.2s ease-in-out;
            font-weight: 500;
            cursor: pointer;
            text-align: center;
            margin-bottom: 5px;
        }
        .sidebar-link:hover {
            background-color: #f0f0f0;
        }
        .sidebar-sep {
            margin: 12px 0;
            border-bottom: 1px solid #ddd;
        }
        .logout-btn {
            color: #ff4b4b;
            font-weight: 600;
            text-align: center;
        }
        .logout-btn:hover {
            background-color: #ffe6e6;
        }
        .profile-container {
            text-align: center;
            margin-bottom: 20px;
        }
        .profile-container img {
            border-radius: 50%;
            width: 100px;
            height: 100px;
            object-fit: cover;
            margin-bottom: 10px;
        }
        .profile-container h3 {
            margin: 0;
            font-size: 18px;
        }
        </style>
    """, unsafe_allow_html=True)

    # --- SIDEBAR ---
    with st.sidebar:
        st.markdown(f"""
            <div class="profile-container">
                <img src="https://cdn-icons-png.flaticon.com/512/847/847969.png" alt="Profilo">
                <h3>👋 Ciao, {user.nome}!</h3>
            </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="sidebar-sep"></div>', unsafe_allow_html=True)

        sidebar_items = [
            ("🏠 Area Personale", "area_personale"),
            ("🧍‍♂️ Visualizza Pazienti", "show_pazienti"),
            ("💬 Chatbot", "chatbot")
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

    # --- Upload PDF ---
    uploaded_file = st.file_uploader("Carica un nuovo documento", type=["pdf"])
    if uploaded_file is not None and not st.session_state[patient_flag_key]:
        file_bytes = uploaded_file.read()

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

        st.session_state[patient_flag_key] = True

    # --- Lista documenti ---
    docs = db.query(Doc).filter(Doc.paziente_email == p.email).all()
    if not docs:
        st.info("Non ci sono documenti caricati per questo paziente.")
        return

    st.markdown("### Documenti caricati:")
    for d in docs:
        st.markdown(f"- **{d.filename}** (ID: {d.id})")

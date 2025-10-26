import streamlit as st
from app.pages_custom.login import login_page
from app.pages_custom.area_personale import area_personale
from app.pages_custom.show_pazienti import show_pazienti
from app.pages_custom.upload_docs import upload_docs
from app.pages_custom.show_docs import show_docs
from app.pages_custom.ask_chatbot import ask_chatbot
from app.database.postgres import SessionLocal, engine, Base

# --- Creazione tabelle se non esistono ---
Base.metadata.create_all(bind=engine)

# --- Configurazione pagina ---
st.set_page_config(page_title="MyNurseAI", layout="centered")

# --- Gestore database ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db = next(get_db())

# --- Inizializza variabili di sessione ---
if "current_page" not in st.session_state:
    st.session_state.current_page = "area_personale"

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "user" not in st.session_state:
    st.session_state.user = None

# --- Controllo login ---
if st.session_state.logged_in and st.session_state.user is not None:
    user = st.session_state.user

    # Navigazione tra pagine
    if st.session_state.current_page == "area_personale":
        area_personale(user,db)
    elif st.session_state.current_page == "show_pazienti":
        # Passa la mail del medico loggato alla funzione show_pazienti
        show_pazienti(db, user)
    elif st.session_state.current_page == "upload_docs":
        upload_docs(db, user)
    elif st.session_state.current_page == "show_docs":
        show_docs(db,user)
    elif st.session_state.current_page == "ask_chatbot":
        ask_chatbot(db,user)
    else:
        # Se current_page contiene un valore non valido, torna all'area personale
        st.session_state.current_page = "area_personale"
        area_personale(user,db)
else:
    # Se non loggato, mostra la pagina di login
    login_page(db)

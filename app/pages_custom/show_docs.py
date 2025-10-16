import streamlit as st
import time
import io
import os
from PyPDF2 import PdfReader
from app.models.doc import Doc

def show_docs(db, user):

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
            ("🧍‍♂️ Visualizza Documenti", "show_pazienti"),
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

    st.title(f"📄 Documenti di {user.nome} {user.cognome}")

    # --- Lista documenti ---
    docs = db.query(Doc).filter(Doc.paziente_email == user.email).all()
    if not docs:
        st.info("Non ci sono documenti caricati per questo paziente.")
        return

    st.markdown("### 📂 Documenti caricati:")

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

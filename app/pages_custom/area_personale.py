import streamlit as st
import time
import os
from app.pages_custom.show_pazienti import show_pazienti


def area_personale(user, db):
    # --- Protezione accesso ---
    if "logged_in" not in st.session_state or not st.session_state.logged_in:
        st.warning("⚠️ Devi prima effettuare il login.")
        st.stop()

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

        # --- Logout ---
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user = None
            st.session_state.show_register = False
            st.query_params.clear()
            st.success("Logout effettuato con successo!")
            time.sleep(1)
            st.rerun()

    # --- CONTENUTO PRINCIPALE ---
    if st.session_state.current_page == "area_personale":
        st.title("🏠 Area Personale")
        st.markdown("""
        Benvenuto nella tua area personale.  
        Qui puoi visualizzare e gestire le informazioni legate al tuo profilo.
        """)
        st.markdown("---")

        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**👤 Username:** {user.username}")
            st.write(f"**📧 Email:** {user.email}")
            st.write(f"**🎂 Data di nascita:** {user.data_nascita}")
            st.write(f"**🚻 Sesso:** {user.sesso}")
        with col2:
            st.write(f"**🏠 Indirizzo:** {user.via} {user.numero_civico}")
            st.write(f"**🏙️ Città:** {user.citta}")
            st.write(f"**📮 CAP:** {user.cap}")
            st.write(f"**💼 Ruolo:** {user.role}")

    elif st.session_state.current_page == "show_pazienti":
        # ✅ Mostra la pagina dei pazienti all’interno dell’area personale
        show_pazienti(db, user)

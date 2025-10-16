import streamlit as st
import time
from app.pages_custom.show_pazienti import show_pazienti  # ✅ import della funzione
from app.models.user import User


def area_personale(user, db):
    # --- Protezione accesso ---
    if "logged_in" not in st.session_state or not st.session_state.logged_in:
        st.warning("⚠️ Devi prima effettuare il login.")
        st.stop()

    # --- STILE PERSONALIZZATO ---
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

        # --- Tutti i bottoni della sidebar uguali nello stile ---
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

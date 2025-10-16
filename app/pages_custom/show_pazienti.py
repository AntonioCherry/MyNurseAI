import streamlit as st
from app.models.user import User
import time

def show_pazienti(db, user):
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

    st.title("🧍‍♂️ Pazienti associati")
    st.markdown(f"### Lista dei pazienti associati a: **{user.username}**")

    pazienti = db.query(User).filter(
        User.medicoAssociato == user.email,
        User.role == "Paziente"
    ).all()

    if not pazienti:
        st.info("Non ci sono pazienti associati a questo medico.")
        return

    if "current_page" not in st.session_state:
        st.session_state.current_page = "show_pazienti"

    # --- LISTA PAZIENTI ---
    for i, p in enumerate(pazienti):
        col1, col2 = st.columns([6, 1])
        with col1:
            st.button(f"👤 {p.nome} {p.cognome} — {p.email}", key=f"btn_{p.email}", use_container_width=True)
        with col2:
            if st.button("📤", key=f"upload_{p.email}", help="Vai ai documenti del paziente"):
                st.session_state.current_page = "show_docs"
                st.session_state.selected_paziente = p
                st.rerun()

        if i < len(pazienti) - 1:
            st.markdown("<div style='margin:2px 0;border-bottom:1px solid #ddd;'></div>", unsafe_allow_html=True)

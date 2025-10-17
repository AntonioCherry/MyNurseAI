import streamlit as st
import os
from ollama import chat, ChatResponse

# --- Funzione per caricare il "modello" tramite Ollama ---
@st.cache_resource
def load_model():
    return OllamaWrapper(model_name="qwen3:1.7b")

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

# --- Funzione principale della chat ---
def ask_chatbot(user):
    # --- CSS sidebar ---
    css_path = os.path.join("app", "page_styles", "sidebar.css")
    if os.path.exists(css_path):
        with open(css_path) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

    # --- Sidebar ---
    with st.sidebar:
        st.markdown(f"""
            <div class="profile-container">
                <img src="https://cdn-icons-png.flaticon.com/512/847/847969.png" alt="Profilo">
                <h3>👋 Ciao, {user.nome}!</h3>
            </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="sidebar-sep"></div>', unsafe_allow_html=True)

        if user.role == "Medico":
            sidebar_items = [
                ("🏠 Area Personale", "area_personale"),
                ("🧍‍♂️ Visualizza Pazienti", "show_pazienti"),
                ("💬 Chatbot", "ask_chatbot")
            ]
        else:
            sidebar_items = [
                ("🏠 Area Personale", "area_personale"),
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
            st.rerun()

    # --- Titolo Chatbot ---
    st.title("💬 Chat con il tuo infermiere virtuale")

    # --- Carica modello tramite Ollama ---
    chatbot = load_model()

    # --- Memoria chat ---
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # Mostra cronologia chat
    for role, msg in st.session_state.chat_history:
        if role == "user":
            st.markdown(f"🧑‍⚕️ **Tu:** {msg}")
        else:
            st.markdown(f"🤖 **MyNurseAI:** {msg}")

    # Campo input e bottone invia
    if "chat_input" not in st.session_state:
        st.session_state.chat_input = ""

    user_input = st.text_input("Scrivi la tua domanda:", value="", key="chat_input")

    if st.button("💬 Invia"):
        if user_input.strip():
            st.session_state.chat_history.append(("user", user_input))

            with st.spinner("L'infermiere sta pensando..."):
                response = chatbot(user_input)[0]["generated_text"]

            st.session_state.chat_history.append(("bot", response))

            # Non serve resettare chat_input manualmente
            st.rerun()
        else:
            st.warning("⚠️ Inserisci un messaggio prima di inviare.")


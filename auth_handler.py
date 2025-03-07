import streamlit as st
import time
from typing import Optional

class AuthHandler:
    def __init__(self, username: str, password: str):
        """Initialize AuthHandler with credentials."""
        self.username = username
        self.password = password

    def authenticate(self) -> bool:
        """Handle user authentication."""
        st.image("assets/header.png", use_container_width=True)
        st.markdown('<div style="margin: 3em 0;"></div>', unsafe_allow_html=True)
        
        username = st.text_input("Username", key="username_input")
        password = st.text_input("Password", type="password", key="password_input")
        
        if st.button("Login"):
            if username == self.username and password == self.password:
                st.session_state.is_authenticated = True
                st.session_state.user_id = f"user_{hash(username)}"
                self.create_new_session()
                st.rerun()
            else:
                st.error("Invalid username or password")
        
        return st.session_state.is_authenticated

    def logout(self) -> None:
        """Clear session state and logout user."""
        with st.spinner(""):
            time.sleep(1)
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            self.initialize_session_state()
            st.rerun()

    def initialize_session_state(self) -> None:
        """Initialize all session state variables."""
        if 'is_authenticated' not in st.session_state:
            st.session_state.is_authenticated = False
        if 'messages' not in st.session_state:
            st.session_state.messages = []
        if 'session_id' not in st.session_state:
            st.session_state.session_id = None
        if 'user_id' not in st.session_state:
            st.session_state.user_id = None
        if 'current_conversation_id' not in st.session_state:
            st.session_state.current_conversation_id = str(int(time.time()))

    def create_new_session(self) -> None:
        """Create a new chat session."""
        st.session_state.session_id = None
        st.session_state.messages = []
        st.session_state.current_conversation_id = str(int(time.time()))

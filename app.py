import streamlit as st
from auth_handler import AuthHandler
from api_client import APIClient
from ui_components import UIComponents
from sidebar_manager import SidebarManager
from chat_handler import ChatHandler
from chat_history import ChatHistoryManager
from config import PAGE_CONFIG
from dotenv import load_dotenv
import os
from feedback_handler import FeedbackHandler

class ChatApplication:
    def __init__(self):
        """Initialize the chat application and its components."""
        load_dotenv()
        
        self.feedback_handler = FeedbackHandler()
        self.auth_handler = AuthHandler(
            username=os.getenv("CHATBOT_USERNAME"),
            password=os.getenv("CHATBOT_PASSWORD")
        )
        self.api_client = APIClient(os.getenv("API_URL"))
        self.ui_components = UIComponents(feedback_handler=self.feedback_handler)
        self.chat_manager = ChatHistoryManager()
        self.sidebar_manager = SidebarManager(self.chat_manager)
        self.chat_handler = ChatHandler(self.api_client, self.chat_manager)

    def setup_page(self) -> None:
        """Set up the page configuration and layout."""
        st.set_page_config(**PAGE_CONFIG)
        self.ui_components.load_custom_css()
        self.auth_handler.initialize_session_state()
            # Initialize feedback states
        if 'feedback_states' not in st.session_state:
            st.session_state.feedback_states = {}
        # Initialize messages if they don't exist
        if 'messages' not in st.session_state:
            st.session_state.messages = []

    def display_header(self) -> None:
        """Display the application header with logout button."""
        col1, col2 = st.columns([0.9, 0.1])
        with col1:
            st.image("assets/header.png", use_container_width=True)
        with col2:
            if st.button("X", help="Logout", use_container_width=True):
                self.auth_handler.logout()

    def main(self) -> None:
        """Main application loop."""
        self.setup_page()

        if not st.session_state.is_authenticated:
            if not self.auth_handler.authenticate():
                return

        self.display_header()
        self.sidebar_manager.create_sidebar()
        self.ui_components.display_chat_messages(st.session_state.messages)

        if prompt := st.chat_input("Ask your question...", key="chat_input"):
            self.chat_handler.handle_chat_input(prompt)

if __name__ == "__main__":
    app = ChatApplication()
    app.main()

import streamlit as st
from datetime import datetime, timedelta
from typing import List, Dict, Any
import time

class SidebarManager:
    def __init__(self, chat_manager):
        """Initialize SidebarManager with ChatHistoryManager."""
        self.chat_manager = chat_manager

    def create_sidebar(self) -> None:
        """Create and manage the sidebar with chat history."""
        with st.sidebar:
            main_container = st.container()
            
            with main_container:
                if st.button("➕ New Chat", 
                            type="primary", 
                            use_container_width=True,
                            help="Start a new chat"):
                    self.create_new_session()
                    st.rerun()

                st.divider()
                
                conversations = self.chat_manager.get_conversations(st.session_state.user_id)
                if not conversations:
                    st.info("No chat history available")
                    return

                shown_conversations = set()
                
                sections = {
                    "Today": 1,
                    "Yesterday": 2,
                    "Previous 7 days": 7,
                    "Previous 30 days": 30
                }

                self._display_conversation_sections(sections, conversations, shown_conversations)

    def _display_section(self, section: str, section_conversations: Dict[str, Dict], 
                        shown_conversations: set) -> None:
        """Display a section of conversations in the sidebar."""
        with st.expander(section, expanded=False):
            for date, convs in section_conversations.items():
                st.markdown(f"**{date}**")
                for conv_id, messages in convs.items():
                    if conv_id not in shown_conversations:
                        first_message = messages[0]["content"]
                        title = first_message[:30] + "..." if len(first_message) > 30 else first_message
                        
                        col1, col2 = st.columns([0.8, 0.2])
                        with col1:
                            if st.button(title, 
                                       key=f"conv_{conv_id}", 
                                       use_container_width=True):
                                self.load_conversation(messages)
                        
                        with col2:
                            if st.button("🗑️", 
                                       key=f"del_{conv_id}",
                                       help="Delete conversation",
                                       use_container_width=True):
                                self.delete_conversation(conv_id)
                        
                        shown_conversations.add(conv_id)

    def _display_conversation_sections(self, sections: Dict[str, int], 
                                    conversations: Dict[str, Dict], 
                                    shown_conversations: set) -> None:
        """Display conversation sections in sidebar."""
        for section, days in sections.items():
            end_date = datetime.now()
            if section == "Yesterday":
                end_date = end_date - timedelta(days=1)
                start_date = end_date
            else:
                start_date = end_date - timedelta(days=days)
            
            section_conversations = self._filter_conversations(
                conversations, start_date, end_date, shown_conversations
            )

            if section_conversations:
                self._display_section(section, section_conversations, shown_conversations)

    def _filter_conversations(self, conversations: Dict[str, Dict], 
                            start_date: datetime, 
                            end_date: datetime,
                            shown_conversations: set) -> Dict[str, Dict]:
        """Filter conversations for a specific date range."""
        section_conversations = {}
        for date, convs in conversations.items():
            conv_date = datetime.strptime(date, '%Y-%m-%d')
            if start_date.date() <= conv_date.date() <= end_date.date():
                filtered_convs = {
                    conv_id: msgs for conv_id, msgs in convs.items()
                    if conv_id not in shown_conversations
                }
                if filtered_convs:
                    section_conversations[date] = filtered_convs
        return section_conversations

    def load_conversation(self, messages: List[Dict[str, Any]]) -> None:
        """Load a conversation into the chat interface."""
        try:
            st.session_state.messages = []
            for msg in messages:
                st.session_state.messages.append({
                    "role": msg["role"],
                    "content": msg["content"],
                    "references": msg.get("references", [])
                })
            st.session_state.current_conversation_id = messages[0]["conversation_id"]
            st.rerun()
        except Exception as e:
            st.error(f"Error loading conversation: {str(e)}")

    def delete_conversation(self, conversation_id: str) -> None:
        """Delete a conversation and refresh the interface."""
        if self.chat_manager.delete_conversation(st.session_state.user_id, conversation_id):
            if st.session_state.current_conversation_id == conversation_id:
                self.create_new_session()
            st.rerun()

    def create_new_session(self) -> None:
        """Create a new chat session."""
        st.session_state.session_id = None
        st.session_state.messages = []
        st.session_state.current_conversation_id = str(int(time.time()))

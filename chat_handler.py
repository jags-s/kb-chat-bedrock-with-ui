import streamlit as st
from typing import Dict, Any
import json

class ChatHandler:
    def __init__(self, api_client, chat_manager):
        """Initialize ChatHandler with APIClient and ChatHistoryManager."""
        self.api_client = api_client
        self.chat_manager = chat_manager

    def handle_chat_input(self, user_input: str) -> None:
        """Process new chat input and get AI response."""
        user_message = {
            "role": "user",
            "content": user_input,
            "session_id": st.session_state.session_id,
            "conversation_id": st.session_state.current_conversation_id
        }
        
        if self.chat_manager.save_chat(st.session_state.user_id, user_message):
            st.session_state.messages.append(user_message)
            
            with st.spinner("Processing your request..."):
                result = self.api_client.call_api(user_input, st.session_state.session_id)
                
            if result:
                self._process_api_response(result)
            else:
                self._handle_error_response()

    def _process_api_response(self, result: Dict[str, Any]) -> None:
        """Process successful API response."""
        if isinstance(result, str):
            result = json.loads(result)
        if 'body' in result:
            result = json.loads(result['body'])
            
        response_content = result.get('generated_response', 'No response available')
        detailed_references = result.get('detailed_references', [])
        
        if 'sessionId' in result:
            st.session_state.session_id = result['sessionId']
        
        assistant_message = {
            "role": "assistant",
            "content": response_content,
            "references": detailed_references,
            "session_id": st.session_state.session_id,
            "conversation_id": st.session_state.current_conversation_id
        }
        
        if self.chat_manager.save_chat(st.session_state.user_id, assistant_message):
            st.session_state.messages.append(assistant_message)
            st.rerun()

    def _handle_error_response(self) -> None:
        """Handle API error response."""
        error_message = {
            "role": "assistant",
            "content": "Failed to get a valid response from the API.",
            "references": [],
            "session_id": st.session_state.session_id,
            "conversation_id": st.session_state.current_conversation_id
        }
        
        if self.chat_manager.save_chat(st.session_state.user_id, error_message):
            st.session_state.messages.append(error_message)
            st.rerun()

import streamlit as st
from typing import List, Dict, Any

class UIComponents:
    
    def __init__(self, feedback_handler=None):
        self.feedback_handler = feedback_handler
        
    @staticmethod
    def load_custom_css() -> None:
        """Load custom CSS styles from external file."""
        with open('.streamlit/styles.css') as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

    def display_chat_messages(self, messages: List[Dict[str, Any]]) -> None:
        """Display chat messages in the main window."""
        for idx, message in enumerate(messages):
            role = message["role"]
            content = message["content"]
            references = message.get("references", [])
            
            message_class = "user-message" if role == "user" else "assistant-message"
            st.markdown(f'<div class="{message_class}">{content}</div>', unsafe_allow_html=True)
            
        if role == "assistant":
            self._display_feedback_buttons(idx, message)
            if references:
                self.show_references(references, idx)

    @staticmethod
    def show_references(references: List[Dict[str, Any]], message_idx: int) -> None:
        """Display references in a compact horizontal list format."""
        if not references:
            return

        ref_key = f"selected_ref_{message_idx}"
        button_key = f"ref_button_clicked_{message_idx}"
        
        if ref_key not in st.session_state:
            st.session_state[ref_key] = 0
        if button_key not in st.session_state:
            st.session_state[button_key] = False

        with st.expander("📚 References", expanded=False):
            cols = st.columns(len(references))
            
            for i, col in enumerate(cols):
                with col:
                    if st.button(
                        f"Reference {i+1}", 
                        key=f"ref_btn_{message_idx}_{i}",
                        help=f"View Reference {i+1} details",
                        use_container_width=True
                    ):
                        st.session_state[ref_key] = i
                        st.session_state[button_key] = True
            
            if 0 <= st.session_state[ref_key] < len(references):
                selected_ref = references[st.session_state[ref_key]]
                UIComponents.display_reference_details(selected_ref)

    @staticmethod
    def display_reference_details(ref: Dict[str, Any]) -> None:
        """Display details for a single reference."""
        st.markdown('<div class="reference-container">', unsafe_allow_html=True)
        
        if uri := ref.get('uri'):
            st.markdown(
                f'''
                <div class="reference-section">
                    <div class="reference-section-title">Source:</div>
                    <div class="reference-uri">{uri}</div>
                </div>
                ''', 
                unsafe_allow_html=True
            )
        
        if snippet := ref.get('snippet'):
            st.markdown(
                f'''
                <div class="reference-section">
                    <div class="reference-section-title">Excerpt:</div>
                    <div class="reference-snippet">{snippet}</div>
                </div>
                ''', 
                unsafe_allow_html=True
            )
        
        if presigned_url := ref.get('presigned_url'):
            st.markdown(
                f'''
                <div class="reference-footer">
                    <a href="{presigned_url}" target="_blank">View Source Document</a>
                    <p>Note: Source document link expires in 1 hour</p>
                </div>
                ''', 
                unsafe_allow_html=True
            )
        
        st.markdown('</div>', unsafe_allow_html=True)


    def display_chat_messages(self, messages: List[Dict[str, Any]]) -> None:
        """Display chat messages in the main window."""
        if not messages:  # Check if messages is empty
            return
            
        for idx, message in enumerate(messages):
            if not isinstance(message, dict):  # Validate message format
                continue
                
            role = message.get("role")  # Use .get() to safely access dict keys
            content = message.get("content", "")
            references = message.get("references", [])
            
            if not role:  # Skip if role is missing
                continue
                
            message_class = "user-message" if role == "user" else "assistant-message"
            st.markdown(f'<div class="{message_class}">{content}</div>', unsafe_allow_html=True)
            
            # Only show feedback buttons for assistant messages
            if role == "assistant":
                self._display_feedback_buttons(idx, message)
                if references:
                    self.show_references(references, idx)


    def _display_feedback_buttons(self, idx, message):
        col1, col2, col3 = st.columns([0.1, 0.1, 0.8])
        
        # Check if feedback has already been given for this message
        if 'feedback_states' not in st.session_state:
            st.session_state.feedback_states = {}
        
        if idx not in st.session_state.feedback_states:
            with col1:
                if st.button("👍", key=f"thumbsup_{idx}"):
                    if self.feedback_handler:
                        self.feedback_handler.handle_feedback(idx, "up", message["content"])
                    st.session_state.feedback_states[idx] = "up"
                    st.rerun()
            
            with col2:
                if st.button("👎", key=f"thumbsdown_{idx}"):
                    if self.feedback_handler:
                        self.feedback_handler.handle_feedback(idx, "down", message["content"])
                    st.session_state.feedback_states[idx] = "down"
                    if 'show_feedback_categories' not in st.session_state:
                        st.session_state.show_feedback_categories = {}
                    st.session_state.show_feedback_categories[idx] = True
                    st.rerun()
        
        # Display feedback categories if negative feedback was given
        if (
            'show_feedback_categories' in st.session_state 
            and idx in st.session_state.show_feedback_categories 
            and st.session_state.show_feedback_categories[idx]
        ):
            self._display_feedback_categories(idx, message)



    def _display_feedback_categories(self, idx: int, message: Dict[str, Any]) -> None:
        """Display feedback categories with checkboxes and text input for negative feedback."""
        # st.markdown("#### Please help us improve by selecting the issues:")
        st.write("Please help us improve by selecting the issues:")
        # Define feedback categories with checkboxes
        feedback_categories = {
            "Incorrect Information": st.checkbox("Incorrect Information", key=f"cat1_{idx}"),
            "Incomplete Answer": st.checkbox("Incomplete Answer", key=f"cat2_{idx}"),
            "Not Relevant": st.checkbox("Not Relevant", key=f"cat3_{idx}"),
            "Unclear Response": st.checkbox("Unclear Response", key=f"cat4_{idx}"),
            "Other": st.checkbox("Other", key=f"cat5_{idx}")
        }
        
        # Text area for detailed feedback
        correction = st.text_area(
            "Please provide the correct information or additional details (optional):",
            key=f"correction_{idx}"
        )
        
        col1, col2 = st.columns([0.2, 0.8])
        with col1:
            # Submit button
            if st.button("Submit", key=f"submit_feedback_{idx}"):
                selected_categories = [
                    cat for cat, selected in feedback_categories.items() 
                    if selected
                ]
                if self.feedback_handler:
                    self.feedback_handler.submit_negative_feedback(
                        idx,
                        message["content"],
                        selected_categories,
                        correction
                    )
                st.session_state.show_feedback_categories[idx] = False
                st.rerun()
        
        with col2:
            # Cancel button
            if st.button("Cancel", key=f"cancel_feedback_{idx}"):
                st.session_state.show_feedback_categories[idx] = False
                st.rerun()

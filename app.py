import streamlit as st
import requests
import json
import os
import time
from dotenv import load_dotenv
from datetime import datetime, timedelta
from chat_history import ChatHistoryManager

# Load environment variables from .env file
load_dotenv()
USERNAME = os.getenv("CHATBOT_USERNAME")
PASSWORD = os.getenv("CHATBOT_PASSWORD")
API_URL = os.getenv("API_URL")

# Initialize ChatHistoryManager
chat_manager = ChatHistoryManager()

# SS brand colors
SS_BLUE = "#001aff"
SS_NAVY = "#002A5C"
SS_LIGHT_BLUE = "#E6F3FA"
SS_GRAY = "#F5F5F5"

def load_custom_css():
    """Load custom CSS styles from external file"""
    with open('.streamlit/styles.css') as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

def initialize_session_state():
    """Initialize all session state variables"""
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

def authenticate():
    """Handle user authentication"""
    st.image("assets/header.png", use_container_width=True)
    st.markdown('<div style="margin: 3em 0;"></div>', unsafe_allow_html=True)
    
    username = st.text_input("Username", key="username_input")
    password = st.text_input("Password", type="password", key="password_input")
    
    if st.button("Login"):
        if username == USERNAME and password == PASSWORD:
            st.session_state.is_authenticated = True
            st.session_state.user_id = f"user_{hash(username)}"
            create_new_session()
            st.rerun()
        else:
            st.error("Invalid username or password")
    
    return st.session_state.is_authenticated

def create_new_session():
    """Create a new chat session"""
    st.session_state.session_id = None
    st.session_state.messages = []
    st.session_state.current_conversation_id = str(int(time.time()))

def logout():
    """Clear session state and logout user"""
    with st.spinner('Logging out...'):
        time.sleep(1)
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        initialize_session_state()
        st.rerun()

def call_api(query, session_id=None):
    """Call the Lambda function through API Gateway"""
    try:
        request_body = {
            "user_query": query
        }
        if session_id:
            request_body["sessionId"] = session_id
            
        response = requests.post(
            url=API_URL,
            headers={"Content-Type": "application/json"},
            json=request_body,
            timeout=30
        )
        
        response.raise_for_status()
        return response.json()
        
    except requests.exceptions.RequestException as e:
        print(f"API Error: {str(e)}")
        return None

def display_chat_messages():
    """Display chat messages in the main window"""
    for idx, message in enumerate(st.session_state.messages):
        role = message["role"]
        content = message["content"]
        references = message.get("references", [])
        
        message_class = "user-message" if role == "user" else "assistant-message"
        st.markdown(f'<div class="{message_class}">{content}</div>', unsafe_allow_html=True)
        
        if role == "assistant" and references:
            show_references(references, idx)

def show_references(references, message_idx):
    """Display references in a compact horizontal list format"""
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
            display_reference_details(selected_ref)

def display_reference_details(ref):
    """Display details for a single reference"""
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

def create_sidebar():
    """Create and manage the sidebar with chat history"""
    with st.sidebar:
        st.markdown("### Chat History")
        
        if st.button("+ New Chat", use_container_width=True):
            create_new_session()
            st.rerun()

        st.markdown("---")
        
        sections = {
            "Today": 1,
            "Yesterday": 2,
            "Previous 7 days": 7,
            "Previous 30 days": 30
        }

        conversations = chat_manager.get_conversations(st.session_state.user_id)
        shown_conversations = set()

        for section, days in sections.items():
            st.markdown(f"#### {section}")
            
            end_date = datetime.now()
            if section == "Yesterday":
                end_date = end_date - timedelta(days=1)
                start_date = end_date
            else:
                start_date = end_date - timedelta(days=days)
            
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

            if section_conversations:
                for date, convs in sorted(section_conversations.items(), reverse=True):
                    for conv_id, messages in convs.items():
                        if conv_id not in shown_conversations:
                            first_msg = messages[0]['content'][:30] + "..."
                            time_str = datetime.fromtimestamp(messages[0]['timestamp']).strftime('%I:%M %p')
                            display_text = f"{first_msg}\n{time_str}"
                            
                            col1, col2 = st.columns([0.8, 0.2])
                            with col1:
                                if st.button(display_text, key=f"{section}_{conv_id}", use_container_width=True):
                                    load_conversation(messages)
                            with col2:
                                if st.button("🗑️", key=f"del_{section}_{conv_id}"):
                                    delete_conversation(conv_id)
                            
                            shown_conversations.add(conv_id)
            else:
                st.markdown("No chats")

        st.markdown("<br>" * 5, unsafe_allow_html=True)
        if st.button("Logout", use_container_width=True, key="logout_sidebar"):
            logout()
            st.rerun()

def load_conversation(messages):
    """Load a conversation into the chat interface"""
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

def delete_conversation(conversation_id):
    """Delete a conversation and refresh the interface"""
    if chat_manager.delete_conversation(st.session_state.user_id, conversation_id):
        if st.session_state.current_conversation_id == conversation_id:
            create_new_session()
        st.rerun()

def handle_chat_input(user_input: str):
    """Process new chat input and get AI response"""
    user_message = {
        "role": "user",
        "content": user_input,
        "session_id": st.session_state.session_id,
        "conversation_id": st.session_state.current_conversation_id
    }
    
    if chat_manager.save_chat(st.session_state.user_id, user_message):
        st.session_state.messages.append(user_message)
        
        with st.spinner("Processing your request..."):
            result = call_api(user_input, st.session_state.session_id)
            
        if result:
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
            
            if chat_manager.save_chat(st.session_state.user_id, assistant_message):
                st.session_state.messages.append(assistant_message)
                st.rerun()
        else:
            error_message = {
                "role": "assistant",
                "content": "Failed to get a valid response from the API.",
                "references": [],
                "session_id": st.session_state.session_id,
                "conversation_id": st.session_state.current_conversation_id
            }
            
            if chat_manager.save_chat(st.session_state.user_id, error_message):
                st.session_state.messages.append(error_message)
                st.rerun()

def main():
    st.set_page_config(
        page_title="SS AI Assistant",
        page_icon="🤖",
        layout="centered",
        initial_sidebar_state="expanded"
    )
    
    load_custom_css()
    initialize_session_state()

    if not st.session_state.is_authenticated:
        if not authenticate():
            return

    st.image("assets/header.png", use_container_width=True)
    create_sidebar()
    display_chat_messages()

    if prompt := st.chat_input("Ask your question...", key="chat_input"):
        handle_chat_input(prompt)

if __name__ == "__main__":
    main()

import streamlit as st
import os
import json
import requests
from datetime import datetime

# API Configuration
API_URL = os.getenv('API_URL', 'https://kfvngqj2ok.execute-api.us-east-1.amazonaws.com/dev/bedrokChatApiRes')

def apply_custom_css():
    st.markdown("""
        <style>
            .chat-container {
                height: 600px;
                overflow-y: auto;
                padding: 20px;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                background-color: #f8f9fa;
            }
            .chat-input {
                position: sticky;
                bottom: 0;
                background-color: white;
                padding: 20px 0;
            }
            .user-message {
                background-color: #e3f2fd;
                padding: 10px;
                border-radius: 8px;
                margin: 5px 0;
            }
            .assistant-message {
                background-color: #f5f5f5;
                padding: 10px;
                border-radius: 8px;
                margin: 5px 0;
            }
            .reference-container {
                border: 1px solid #ddd;
                padding: 10px;
                margin: 10px 0;
                border-radius: 5px;
            }
            .reference-section {
                margin: 10px 0;
            }
            .reference-section-title {
                font-weight: bold;
                margin-bottom: 5px;
            }
            .reference-uri, .reference-snippet {
                background-color: #f8f9fa;
                padding: 8px;
                border-radius: 4px;
            }
            .reference-footer {
                margin-top: 10px;
                font-size: 0.9em;
            }
            .block-container {
                padding-top: 1rem !important;
            }
            .main-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 1rem;
                background-color: #f8f9fa;
                border-radius: 8px;
                margin-bottom: 1rem;
            }
        </style>
    """, unsafe_allow_html=True)

# Initialize session states
if 'chat_visible' not in st.session_state:
    st.session_state.chat_visible = False
if 'is_authenticated' not in st.session_state:
    st.session_state.is_authenticated = False
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'session_id' not in st.session_state:
    st.session_state.session_id = None

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

def call_api(query, session_id=None):
    """Call the Lambda function through API Gateway"""
    try:
        request_body = {
            "user_query": query
        }
        if session_id:
            request_body["sessionId"] = session_id
            
        print(f"Request Body, url: {request_body}, API_URL: {API_URL}")
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

def authenticate(username, password):
    VALID_USERNAME = os.getenv('VALID_USERNAME', 'admin')
    VALID_PASSWORD = os.getenv('VALID_PASSWORD', 'password')
    
    if username == VALID_USERNAME and password == VALID_PASSWORD:
        st.session_state.is_authenticated = True
        return True
    return False

def clear_chat():
    st.session_state.messages = []
    st.session_state.session_id = None

def logout():
    st.session_state.is_authenticated = False
    st.session_state.messages = []
    st.session_state.chat_visible = False
    st.session_state.session_id = None

def display_chat_messages():
    for idx, message in enumerate(st.session_state.messages):
        message_class = "user-message" if message["role"] == "user" else "assistant-message"
        st.markdown(f'<div class="{message_class}">{message["content"]}</div>', unsafe_allow_html=True)
        
        if message["role"] == "assistant" and "references" in message:
            show_references(message["references"], idx)

def handle_chat_input(user_input):
    if user_input:
        # Add user message
        st.session_state.messages.append({
            "role": "user",
            "content": user_input,
            "timestamp": datetime.now().strftime("%H:%M")
        })
        
        # Process the message and generate response
        with st.spinner("Processing your request..."):
            api_response = call_api(user_input, st.session_state.session_id)
            
            if api_response:
                if isinstance(api_response, str):
                    api_response = json.loads(api_response)
                if 'body' in api_response:
                    api_response = json.loads(api_response['body'])
                
                response_content = api_response.get('generated_response', 'No response available')
                detailed_references = api_response.get('detailed_references', [])
                
                if 'sessionId' in api_response:
                    st.session_state.session_id = api_response['sessionId']
                
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response_content,
                    "references": detailed_references,
                    "timestamp": datetime.now().strftime("%H:%M")
                })
            else:
                st.error("Failed to get response from API")

def create_layout():
    with st.container():
        header_col, _, chat_button_col = st.columns([0.7, 0.2, 0.1])
        
        with header_col:
            st.title("Main Content")
        
        with chat_button_col:
            if not st.session_state.chat_visible:
                if st.button("💬 Chat"):
                    st.session_state.chat_visible = True
                    st.rerun()

    if st.session_state.chat_visible:
        main_content, chat_panel = st.columns([0.7, 0.3])
        
        with main_content:
            st.write("This is the main content area")
            st.image("assets/background.png", use_container_width=True)
            
        with chat_panel:
            st.markdown('<div class="chat-container">', unsafe_allow_html=True)
            
            # Chat header
            col1, col2, col3 = st.columns([0.5, 0.3, 0.2])
            with col1:
                st.markdown("""
                    <h2 style='text-align: center; color: #0066cc; margin: 0;'>Chatbot</h2>
                    """, unsafe_allow_html=True)
            with col2:
                if st.button("🔄"):
                    clear_chat()
                    st.rerun()
            with col3:
                if st.button("✕"):
                    logout()
                    st.rerun()
            
            # Login form if not authenticated
            if not st.session_state.is_authenticated:
                with st.form("login_form"):
                    username = st.text_input("Username")
                    password = st.text_input("Password", type="password")
                    submit_button = st.form_submit_button("Login")
                    
                    if submit_button:
                        if authenticate(username, password):
                            st.success("Successfully logged in!")
                            st.rerun()
                        else:
                            st.error("Invalid username or password")
            
            # Chat interface only shown after authentication
            else:
                display_chat_messages()
                
                # Chat input
                st.markdown('<div class="chat-input">', unsafe_allow_html=True)
                user_input = st.chat_input("Ask your question...", key="chat_input")
                if user_input:
                    handle_chat_input(user_input)
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.write("This is the main content area")
        st.image("assets/background.png", use_container_width=True)

def main():
    st.set_page_config(
        page_title="Chat Application",
        page_icon="💬",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    apply_custom_css()
    create_layout()

if __name__ == "__main__":
    main()

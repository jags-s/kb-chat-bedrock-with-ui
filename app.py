import streamlit as st
import requests
import json
import os
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables from .env file
load_dotenv()
USERNAME = os.getenv("CHATBOT_USERNAME")
PASSWORD = os.getenv("CHATBOT_PASSWORD")
API_URL = os.getenv("API_URL")

# SS brand colors
SS_BLUE = "#001aff"
SS_NAVY = "#002A5C"
SS_LIGHT_BLUE = "#E6F3FA"
SS_GRAY = "#F5F5F5"

def load_custom_css():
    """Load custom CSS styles from external file"""
    with open('.streamlit/styles.css') as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

def check_password():
    """Returns `True` if the user had the correct password."""
    def password_entered():
        if st.session_state["username"] == USERNAME and st.session_state["password"] == PASSWORD:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
            del st.session_state["username"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.markdown(f'<div class="chat-header"><h1>SS AI Assistant</h1></div>', unsafe_allow_html=True)
        st.markdown('<div style="margin: 3em 0;"></div>', unsafe_allow_html=True)
        st.text_input("Username", key="username")
        st.text_input("Password", type="password", key="password")
        st.button("Login", on_click=password_entered)
        return False
    
    if not st.session_state["password_correct"]:
        st.markdown(f'<div class="chat-header"><h1>SS AI Assistant</h1></div>', unsafe_allow_html=True)
        st.markdown('<div style="margin: 3em 0;"></div>', unsafe_allow_html=True)
        st.text_input("Username", key="username")
        st.text_input("Password", type="password", key="password")
        st.button("Login", on_click=password_entered)
        st.error("Invalid username or password")
        return False
    
    return True

def display_reference_details(ref):
    """Display details for a single reference"""
    st.markdown('<div class="reference-container">', unsafe_allow_html=True)
    
    # Display S3 URI if available
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
    
    # Display snippet if available
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
    
    # Display source link and expiration if available
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
    
    # Initialize session state variables if they don't exist
    if ref_key not in st.session_state:
        st.session_state[ref_key] = 0
    if button_key not in st.session_state:
        st.session_state[button_key] = False

    with st.expander("📚 References", expanded=False):
        # Create horizontal list of reference buttons
        cols = st.columns(len(references))
        
        for i, col in enumerate(cols):
            with col:
                # Use a unique key for each button
                if st.button(
                    f"Reference {i+1}",
                    key=f"ref_btn_{message_idx}_{i}",
                    help=f"View Reference {i+1} details",
                    use_container_width=True
                ):
                    st.session_state[ref_key] = i
                    st.session_state[button_key] = True
        
        # Only display reference details if we have a valid selection
        if 0 <= st.session_state[ref_key] < len(references):
            selected_ref = references[st.session_state[ref_key]]
            display_reference_details(selected_ref)

# def show_references(references, message_idx):
#     """Display references in a compact horizontal list format"""
#     if not references:
#         return

#     with st.expander("📚 References", expanded=False):
#         ref_key = f"selected_ref_{message_idx}"
        
#         # Initialize reference selection in session state
#         if ref_key not in st.session_state:
#             st.session_state[ref_key] = 0
        
#         # Create horizontal list of reference buttons
#         cols = st.columns(len(references))
        
#         for i, col in enumerate(cols):
#             with col:
#                 if st.button(
#                     f"Reference {i+1}",
#                     key=f"ref_btn_{message_idx}_{i}",
#                     help=f"View Reference {i+1} details"
#                 ):
#                     st.session_state[ref_key] = i
#                     st.rerun()
        
#         # Display selected reference details
#         selected_ref = references[st.session_state[ref_key]]
#         display_reference_details(selected_ref)

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

def main():
    st.set_page_config(
        page_title="SS AI Assistant",
        page_icon="🤖",
        layout="centered",
        initial_sidebar_state="collapsed",
    )
    
    load_custom_css()

    if not check_password():
        return

    st.markdown('<div class="chat-header"><h2>SS AI Assistant</h2></div>', unsafe_allow_html=True)
    st.markdown('<h5 class="sub-title" style="text-align: center; color: #001aff;">SS Employee Concierge</h5>', unsafe_allow_html=True)
    # Initialize session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "session_id" not in st.session_state:
        st.session_state.session_id = None

    # Display chat history
    for idx, message in enumerate(st.session_state.messages):
        role = message["role"]
        content = message["content"]
        references = message.get("references", [])
        
        message_class = "user-message" if role == "user" else "assistant-message"
        st.markdown(f'<div class="{message_class}">{content}</div>', unsafe_allow_html=True)
        
        # Show references for assistant messages with references
        if role == "assistant" and references:
            show_references(references, idx)

    # Chat input and processing
    if prompt := st.chat_input("Ask your question...", key="chat_input"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.rerun()

    # Process last user message if it exists and hasn't been responded to
    if (st.session_state.messages and 
        st.session_state.messages[-1]["role"] == "user"):
        
        with st.spinner("Processing your request..."):
            result = call_api(st.session_state.messages[-1]["content"], 
                            st.session_state.session_id)

        if result:
            if isinstance(result, str):
                result = json.loads(result)
            if 'body' in result:
                result = json.loads(result['body'])
                
            response_content = result.get('generated_response', 'No response available')
            detailed_references = result.get('detailed_references', [])
            
            if 'sessionId' in result:
                st.session_state.session_id = result['sessionId']
            
            st.session_state.messages.append({
                "role": "assistant",
                "content": response_content,
                "references": detailed_references
            })
            st.rerun()
        else:
            error_message = "Failed to get a valid response from the API."
            st.error(error_message)
            st.session_state.messages.append({
                "role": "assistant",
                "content": error_message,
                "references": []
            })
            st.rerun()

if __name__ == "__main__":
    main()

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
MAX_REFERENCES = int(os.getenv("MAX_REFERENCES"))

# Custom CSS for styling
def load_custom_css():
    try:
        with open('.streamlit/styles.css') as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    except Exception as e:
        print(f"Error loading CSS: {e}")

def check_password():
    """Returns `True` if the user had the correct password."""
    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["username"] == USERNAME and st.session_state["password"] == PASSWORD:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store password
            del st.session_state["username"]  # Don't store username
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.markdown('<h1 class="main-title">GHR AI Assistant</h1>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.text_input("Username", key="username")
        st.text_input("Password", type="password", key="password")
        st.button("Login", on_click=password_entered)
        st.markdown('</div>', unsafe_allow_html=True)
        return False
    elif not st.session_state["password_correct"]:
        st.markdown('<h1 class="main-title">GHR AI Assistant</h1>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        st.text_input("Username", key="username")
        st.text_input("Password", type="password", key="password")
        st.button("Login", on_click=password_entered)
        st.error("Invalid username or password")
        st.markdown('</div>', unsafe_allow_html=True)
        return False
    else:
        return True

def format_references(detailed_references, expiration_time=None):
    """Format references as simple HTML links"""
    if not detailed_references:
        return ""
    
    references = detailed_references[:MAX_REFERENCES]
    
    references_html = "<div class='references'><strong>References:</strong><br>"
    
    for i, ref in enumerate(references, 1):
        presigned_url = ref.get('presigned_url', '')
        if presigned_url:
            references_html += f"<a href='{presigned_url}' target='_blank'>Reference {i}</a><br>"
    
    if expiration_time:
        try:
            expiry = datetime.fromisoformat(expiration_time)
            references_html += f"<div class='expiration-time'>Links expire at: {expiry.strftime('%Y-%m-%d %H:%M:%S')} UTC</div>"
        except ValueError:
            pass
    
    references_html += "</div>"
    return references_html

def call_api(query, session_id=None):
    """Call the Lambda function through API Gateway"""
    api_url = API_URL
    headers = {"Content-Type": "application/json"}
    try:
        request_body = {
            "user_query": query
        }
        
        # Include session_id if available
        if session_id:
            request_body["sessionId"] = session_id
            
        print(f"Attempting to call API at: {api_url}")
        print(f"Headers: {headers}")
        print(f"Request body: {request_body}")
        
        response = requests.post(
            url=api_url,
            headers=headers,
            json=request_body,
            timeout=30
        )
        
        response.raise_for_status()
        response_data = response.json()
        
        # Extract data from the API Gateway response format
        if isinstance(response_data, str):
            response_data = json.loads(response_data)
        
        if 'body' in response_data:
            return json.loads(response_data['body'])
        return response_data
        
    except requests.exceptions.ConnectionError as e:
        print(f"Connection Error Details:")
        print(f"Error Type: {type(e).__name__}")
        print(f"Error Message: {str(e)}")
        print(f"API URL: {api_url}")
        return None
        
    except requests.exceptions.Timeout as e:
        print(f"Timeout Error: {str(e)}")
        print(f"Request timed out after 30 seconds")
        return None
        
    except requests.exceptions.RequestException as e:
        print(f"Request Exception Details:")
        print(f"Error Type: {type(e).__name__}")
        print(f"Error Message: {str(e)}")
        if hasattr(e, 'response'):
            print(f"Response Status: {e.response.status_code}")
            print(f"Response Body: {e.response.text}")
        return None

def main():
    st.set_page_config(
        page_title="Just Ask",
        page_icon="🤖",
        layout="centered",
        initial_sidebar_state="collapsed",
    )
    
    load_custom_css()

    if not check_password():
        return

    st.markdown('<h2 class="main-title" style="position: sticky; top: 0; background-color: #001aff; color: white; z-index: 999;text-align: center;">Just Ask</h2>', unsafe_allow_html=True)
    st.markdown('<h5 class="sub-title" style="text-align: center;">SS Employee Concierge</h5>', unsafe_allow_html=True)

    # Initialize session state variables
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "session_id" not in st.session_state:
        st.session_state.session_id = None

    # Display chat history
    for message in st.session_state.messages:
        role = message["role"]
        content = message["content"]
        references = message.get("references", "")
        
        message_class = "user-message" if role == "user" else "assistant-message"
        st.markdown(
            f'<div class="{message_class}">{content}{references}</div>',
            unsafe_allow_html=True
        )

    # Chat input and processing
    if prompt := st.chat_input("Ask your question...", key="chat_input"):
        st.markdown(f'<div class="user-message">{prompt}</div>', unsafe_allow_html=True)
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.spinner("Processing your request..."):
            result = call_api(prompt, st.session_state.session_id)

        if result:
            # Update session ID if provided
            if 'sessionId' in result:
                st.session_state.session_id = result['sessionId']
                
            response_content = result.get('generated_response', 'No response available')
            detailed_references = result.get('detailed_references', [])
            expiration_time = result.get('urlExpirationTime')
            
            references_html = format_references(detailed_references, expiration_time)
            
            st.markdown(
                f'<div class="assistant-message">{response_content}{references_html}</div>',
                unsafe_allow_html=True
            )
            
            st.session_state.messages.append({
                "role": "assistant",
                "content": response_content,
                "references": references_html
            })
        else:
            error_message = "Failed to get a valid response from the API."
            st.error(error_message)
            st.session_state.messages.append({
                "role": "assistant",
                "content": error_message,
                "references": ""
            })

if __name__ == "__main__":
    main()

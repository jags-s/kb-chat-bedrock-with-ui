import streamlit as st
import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
USERNAME = os.getenv("CHATBOT_USERNAME")
PASSWORD = os.getenv("CHATBOT_PASSWORD")
API_URL = os.getenv("API_URL")
MAX_REFERENCES = int(os.getenv("MAX_REFERENCES"))
# SS brand colors
# SS_COLORS = {
#     "primary_blue": "#007AC0",
#     "secondary_blue": "#00508C",
#     "dark_blue": "#002A5C",
#     "light_gray": "#F5F5F5",
#     "text_gray": "#4A4A4A"
# }

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
        # First run, show inputs for username + password.
        # st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
        st.markdown('<h1 class="main-title">GHR AI Concierge</h1>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        # st.markdown('<div class="login-container">', unsafe_allow_html=True)
        # st.markdown('<h2 class="login-title">Login Required</h2>', unsafe_allow_html=True)
        st.text_input("Username", key="username")
        st.text_input("Password", type="password", key="password")
        st.button("Login", on_click=password_entered)
        st.markdown('</div>', unsafe_allow_html=True)
        return False
    elif not st.session_state["password_correct"]:
        # Password not correct, show input + error.
        # st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
        st.markdown('<h1 class="main-title">GHR AI Assistant</h1>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        # st.markdown('<div class="login-container">', unsafe_allow_html=True)
        # st.markdown('<h2 class="login-title">Login Required</h2>', unsafe_allow_html=True)
        st.text_input("Username", key="username")
        st.text_input("Password", type="password", key="password")
        st.button("Login", on_click=password_entered)
        st.error("😕 Invalid username or password")
        st.markdown('</div>', unsafe_allow_html=True)
        return False
    else:
        # Password correct.
        return True

# Function to call the API

def call_api(query):
    api_url = API_URL
    headers = {"Content-Type": "application/json"}
    try:
        print(f"Attempting to call API at: {api_url}")
        print(f"Headers: {headers}")
        print(f"Request body: {{'user_query': query}}")
        
        response = requests.post(
            url=api_url,
            headers=headers,
            json={"user_query": query},
            timeout=30  # Add timeout
        )
        
        response.raise_for_status()
        return response.json()
        
    except requests.exceptions.ConnectionError as e:
        print(f"Connection Error: {str(e)}")
        print(f"Unable to connect to {api_url}")
        return None
        
    except requests.exceptions.Timeout as e:
        print(f"Timeout Error: {str(e)}")
        print(f"Request timed out after 30 seconds")
        return None
        
    except requests.exceptions.RequestException as e:
        print(f"Request Exception Details:")
        print(f"Error Type: {type(e).__name__}")
        print(f"Error Message: {str(e)}")
        print(f"Request URL: {e.request.url if e.request else 'N/A'}")
        print(f"Request Headers: {e.request.headers if e.request else 'N/A'}")
        print(f"Request Body: {e.request.body if e.request else 'N/A'}")
        if hasattr(e.response, 'status_code'):
            print(f"Response Status: {e.response.status_code}")
            print(f"Response Body: {e.response.text}")
        return None

# def call_api(query):
#     api_url = API_URL
#     headers = {"Content-Type": "application/json"}
#     try:
#         response = requests.post(url=api_url, headers=headers, json={"user_query": query})

#         print("response.status_code", response.status_code)
#         if response.status_code == 400:
#             print("Bad Request - Check payload format")
#             print(f"Response: {response.text}")
#         elif response.status_code == 401:
#             print("Unauthorized - Check authentication")
#             print(f"Headers sent: {response.request.headers}")
#         elif response.status_code == 403:
#             print("Forbidden - Check permissions")
#         elif response.status_code == 404:
#             print(f"Not Found - Check URL: {API_URL}")
#         elif response.status_code == 429:
#             print("Rate limit exceeded")
        
#         response.raise_for_status()
#         return response.json()
#     except requests.exceptions.RequestException as e:
#         st.error(f"An error occurred while calling the API: {str(e)}")
#         return None
#     except json.JSONDecodeError as e:
#         st.error(f"Error decoding JSON response: {str(e)}")
#         return None

# Function to format S3 location as a clickable link
def format_references(s3_location):
    if not s3_location or s3_location == 'N/A':
        return ""
    
    references = s3_location.split(',') if isinstance(s3_location, str) else []
    
    if not references:
        return ""

    # Limit the number of references
    references = references[:MAX_REFERENCES]
    
    references_html = "<div class='references'><strong>References:</strong><br>"
    for i, ref in enumerate(references, 1):
        ref = ref.strip()
        if ref:
            references_html += f"<a href='{ref}' target='_blank'>Reference {i}</a><br>"
    
    # Add indication if there are more references
    original_count = len(s3_location.split(','))
    if original_count > MAX_REFERENCES:
        references_html += f"<em>({original_count - MAX_REFERENCES} more references available)</em><br>"
    
    references_html += "</div>"
    
    return references_html


# Streamlit app
def main():

    st.set_page_config(
        page_title="Just Ask",
        page_icon="🤖",
        layout="centered",
        initial_sidebar_state="collapsed",
    )
    # Load custom CSS
    load_custom_css()

    # Check authentication before proceeding
    if not check_password():
        return

    
    # Custom title with SS branding
    # st.markdown('<h1 class="main-title" style="position: sticky; top: 0; background-color: white; z-index: 999;">Just Ask</h1>', unsafe_allow_html=True)
    st.markdown('<h2 class="main-title" style="position: sticky; top: 0; background-color: #001aff; color: white; z-index: 999;text-align: center;"> ✨ Just Ask</h2>', unsafe_allow_html=True)
    st.markdown('<h5 class="sub-title" style="text-align: center;">SS Employee Concierge</h5>', unsafe_allow_html=True)


    # st.markdown('<h1 class="main-title">Just Ask</h1>', unsafe_allow_html=True)
    # st.markdown('<h1 class="main-title" style="background-color: #f0f0f0; padding: 20px; border-radius: 5px;">Just Ask</h1>', unsafe_allow_html=True)

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat messages from history
    for message in st.session_state.messages:
        role = message["role"]
        content = message["content"]
        references = message.get("references", "")
        
        message_class = "user-message" if role == "user" else "assistant-message"
        st.markdown(
            f'<div class="{message_class}">{content}{references}</div>',
            unsafe_allow_html=True
        )

    # Chat input at the bottom
    if prompt := st.chat_input("Ask your question...", key="chat_input"):
        st.markdown(f'<div class="user-message">{prompt}</div>', unsafe_allow_html=True)
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.spinner("Processing your request..."):
            result = call_api(prompt)

        if result:
            response_content = result.get('generated_response', 'No response available')
            references_html = format_references(result.get('s3_location', ''))
            
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

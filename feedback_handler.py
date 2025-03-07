import boto3
from datetime import datetime
import uuid
import streamlit as st
from typing import List, Dict, Any

class FeedbackHandler:
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb')
        self.feedback_table = self.dynamodb.Table('ChatFeedback')
        self._create_feedback_table()
        self._initialize_session_state()

    def _initialize_session_state(self):
        """Initialize feedback-related session states"""
        if 'feedback_states' not in st.session_state:
            st.session_state.feedback_states = {}
        if 'show_feedback_categories' not in st.session_state:
            st.session_state.show_feedback_categories = {}
        if 'selected_category' not in st.session_state:
            st.session_state.selected_category = {}

    def _create_feedback_table(self):
        """Create DynamoDB table for feedback if it doesn't exist"""
        try:
            self.dynamodb.create_table(
                TableName='ChatFeedback',
                KeySchema=[
                    {'AttributeName': 'feedback_id', 'KeyType': 'HASH'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'feedback_id', 'AttributeType': 'S'}
                ],
                ProvisionedThroughput={
                    'ReadCapacityUnits': 5,
                    'WriteCapacityUnits': 5
                }
            )
        except self.dynamodb.meta.client.exceptions.ResourceInUseException:
            # Table already exists
            pass
        except Exception as e:
            st.error(f"Error creating DynamoDB table: {str(e)}")

    def handle_feedback(self, idx, feedback_type, message_content):
        """Handle feedback button clicks"""
        try:
            st.session_state.feedback_states[idx] = feedback_type
            
            if feedback_type == "down":
                st.session_state.show_feedback_categories[idx] = True
            else:
                self._store_feedback(
                    message_idx=idx,
                    feedback_type="positive",
                    message_content=message_content
                )
        except Exception as e:
            st.error(f"Error handling feedback: {str(e)}")

    def handle_category_feedback(self, message_idx: int, category: str, message_content: str) -> None:
        """Handle the category feedback for negative responses"""
        try:
            self._store_feedback(
                message_idx=message_idx,
                feedback_type="negative",
                message_content=message_content,
                categories=[category]
            )
            st.session_state.selected_category[message_idx] = category
            st.session_state.show_feedback_categories[message_idx] = False
        except Exception as e:
            st.error(f"Error handling category feedback: {str(e)}")

    def submit_negative_feedback(self, idx: int, message_content: str, selected_categories: List[str], correction: str) -> None:
        """Submit negative feedback with categories and correction"""
        try:
            self._store_feedback(
                message_idx=idx,
                feedback_type="negative",
                message_content=message_content,
                categories=selected_categories,
                correction=correction if correction.strip() else None
            )
            
            st.session_state.feedback_states[idx] = "down"
            st.session_state.show_feedback_categories[idx] = False
            
        except Exception as e:
            st.error(f"Error submitting feedback: {str(e)}")


    def _store_feedback(self, message_idx, feedback_type, message_content, categories=None, correction=None):
        """Store feedback in DynamoDB"""
        try:
            feedback_item = {
                'feedback_id': str(uuid.uuid4()),
                'timestamp': datetime.now().isoformat(),
                'session_id': st.session_state.get('session_id', str(uuid.uuid4())),
                'message_idx': message_idx,
                'feedback_type': feedback_type,
                'message_content': message_content,
                'user_id': st.session_state.get('user_id', 'anonymous')
            }

            if categories:
                feedback_item['categories'] = categories
            if correction:
                feedback_item['correction'] = correction

            self.feedback_table.put_item(Item=feedback_item)
            
        except Exception as e:
            st.error(f"Error storing feedback: {str(e)}")

    def clear_feedback_state(self):
        """Clear feedback-related session states"""
        st.session_state.feedback_states = {}
        st.session_state.show_feedback_categories = {}
        st.session_state.selected_category = {}

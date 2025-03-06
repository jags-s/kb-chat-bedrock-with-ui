import boto3
from datetime import datetime, timedelta
import time
from typing import List, Dict
import json
from decimal import Decimal
from boto3.dynamodb.conditions import Key
from dotenv import load_dotenv
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ChatHistoryManager:
    def __init__(self):
        # Load environment variables
        load_dotenv()
        
        # Get AWS credentials from environment variables
        aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
        aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        aws_region = os.getenv('AWS_REGION')
        
        if not all([aws_access_key_id, aws_secret_access_key, aws_region]):
            raise ValueError("AWS credentials not found in environment variables")
        
        # Initialize DynamoDB resource
        self.dynamodb = boto3.resource(
            'dynamodb',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=aws_region
        )
        
        self.table = self.dynamodb.Table('ChatHistory')

    def save_chat(self, user_id: str, message: dict) -> bool:
        """
        Save a chat message to DynamoDB
        """
        try:
            # Convert timestamp to Decimal
            timestamp = Decimal(str(time.time()))
            
            # Prepare the item
            item = {
                'user_id': user_id,
                'timestamp': timestamp,
                'content': message['content'],
                'role': message['role'],
                'date': datetime.fromtimestamp(float(timestamp)).strftime('%Y-%m-%d'),
                'session_id': message.get('session_id'),
                'references': json.dumps(message.get('references', [])),
                'conversation_id': message.get('conversation_id', str(int(float(timestamp))))
            }
            
            # Print debug information
            # logger.info(f"Saving item to DynamoDB: {json.dumps(item, default=str)}")
            
            # Attempt to save
            response = self.table.put_item(Item=item)
            
            # Check response
            if response['ResponseMetadata']['HTTPStatusCode'] == 200:
                logger.info(f"Successfully saved message for user {user_id}")
                return True
            else:
                logger.error(f"Error saving message. Response: {json.dumps(response, default=str)}")
                return False
                
        except Exception as e:
            logger.error(f"Error saving chat: {str(e)}")
            logger.error(f"Message content: {json.dumps(message, default=str)}")
            return False

    def get_conversations(self, user_id: str, days: int = None) -> Dict[str, List[Dict]]:
        """
        Get conversations grouped by date and conversation_id
        """
        try:
            if days:
                cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
                response = self.table.query(
                    KeyConditionExpression=Key('user_id').eq(user_id),
                    FilterExpression='#date >= :cutoff',
                    ExpressionAttributeValues={
                        ':cutoff': cutoff_date
                    },
                    ExpressionAttributeNames={
                        '#date': 'date'
                    }
                )
            else:
                response = self.table.query(
                    KeyConditionExpression=Key('user_id').eq(user_id)
                )

            items = response.get('Items', [])
            
            # Group by date and conversation_id
            conversations = {}
            for item in items:
                # Convert Decimal to float for timestamp
                item['timestamp'] = float(item['timestamp'])
                
                date = item['date']
                conv_id = item['conversation_id']
                
                if date not in conversations:
                    conversations[date] = {}
                
                if conv_id not in conversations[date]:
                    conversations[date][conv_id] = []
                
                # Parse references back to list
                if 'references' in item:
                    item['references'] = json.loads(item['references'])
                
                conversations[date][conv_id].append(item)

            # Sort conversations by timestamp
            for date in conversations:
                for conv_id in conversations[date]:
                    conversations[date][conv_id].sort(key=lambda x: x['timestamp'])

            return conversations
        except Exception as e:
            logger.error(f"Error getting conversations: {str(e)}")
            return {}

    
    # Add this method to ChatHistoryManager class
    def get_conversation_summaries(self, user_id: str) -> List[Dict]:
        """
        Get a summary of all conversations for the sidebar
        """
        try:
            response = self.table.query(
                KeyConditionExpression=Key('user_id').eq(user_id)
            )
            
            items = response.get('Items', [])
            conversations = {}
            
            for item in items:
                conv_id = item['conversation_id']
                if conv_id not in conversations:
                    conversations[conv_id] = {
                        'conversation_id': conv_id,
                        'date': item['date'],
                        'first_message': item['content'][:50] + '...',  # Preview of first message
                        'timestamp': float(item['timestamp'])
                    }
            
            # Convert to list and sort by timestamp (newest first)
            conversation_list = list(conversations.values())
            conversation_list.sort(key=lambda x: x['timestamp'], reverse=True)
            
            return conversation_list
        except Exception as e:
            logger.error(f"Error getting conversation summaries: {str(e)}")
            return []

    def delete_conversation(self, user_id: str, conversation_id: str) -> bool:
        """
        Delete an entire conversation
        """
        try:
            # Query all messages in the conversation
            response = self.table.query(
                KeyConditionExpression=Key('user_id').eq(user_id),
                FilterExpression='conversation_id = :cid',
                ExpressionAttributeValues={
                    ':cid': conversation_id
                }
            )

            # Delete each message
            for item in response.get('Items', []):
                self.table.delete_item(
                    Key={
                        'user_id': user_id,
                        'timestamp': item['timestamp']
                    }
                )
            return True
        except Exception as e:
            logger.error(f"Error deleting conversation: {str(e)}")
            return False

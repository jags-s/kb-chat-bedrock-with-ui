from chat_history import ChatHistoryManager
import time
import os
from dotenv import load_dotenv
import boto3
from botocore.exceptions import ClientError
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def ensure_table_exists():
    """Ensure the DynamoDB table exists before testing"""
    try:
        # Load environment variables
        load_dotenv()
        
        # Get AWS credentials
        aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
        aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        aws_region = os.getenv('AWS_REGION')
        
        if not all([aws_access_key_id, aws_secret_access_key, aws_region]):
            raise ValueError("AWS credentials not found in environment variables")
        
        # Initialize DynamoDB
        dynamodb = boto3.resource(
            'dynamodb',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=aws_region
        )
        
        # Try to create table if it doesn't exist
        table_name = 'ChatHistory'
        try:
            table = dynamodb.create_table(
                TableName=table_name,
                KeySchema=[
                    {
                        'AttributeName': 'user_id',
                        'KeyType': 'HASH'  # Partition key
                    },
                    {
                        'AttributeName': 'timestamp',
                        'KeyType': 'RANGE'  # Sort key
                    }
                ],
                AttributeDefinitions=[
                    {
                        'AttributeName': 'user_id',
                        'AttributeType': 'S'
                    },
                    {
                        'AttributeName': 'timestamp',
                        'AttributeType': 'N'
                    }
                ],
                BillingMode='PAY_PER_REQUEST'
            )
            logger.info(f"Creating table {table_name}...")
            table.wait_until_exists()
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceInUseException':
                logger.info(f"Table {table_name} already exists")
            else:
                raise e
                
        return True
    except Exception as e:
        logger.error(f"Error ensuring table exists: {str(e)}")
        return False

def test_chat_storage():
    """Test chat storage functionality"""
    try:
        # First ensure table exists
        if not ensure_table_exists():
            logger.error("Failed to ensure table exists")
            return
        
        # Initialize chat manager
        chat_manager = ChatHistoryManager()
        
        # Generate test user_id
        user_id = f"test_user_{int(time.time())}"
        
        # Test message
        test_message = {
            "role": "user",
            "content": "This is a test message",
            "session_id": "test_session",
            "conversation_id": "test_conversation"
        }
        
        # Try to save the message
        logger.info(f"Attempting to save test message for user {user_id}")
        success = chat_manager.save_chat(user_id, test_message)  # Using save_chat instead of save_message
        
        if success:
            logger.info("Message saved successfully")
            
            # Try to retrieve the message
            conversations = chat_manager.get_conversations(user_id)
            if conversations:
                logger.info("Retrieved conversations:")
                for date, convs in conversations.items():
                    print(f"\nDate: {date}")
                    for conv_id, messages in convs.items():
                        print(f"\nConversation ID: {conv_id}")
                        for msg in messages:
                            print("\nMessage Details:")
                            print("-" * 50)
                            print(f"Role: {msg['role']}")
                            print(f"Content: {msg['content']}")
                            print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(msg['timestamp']))}")
                            print(f"Session ID: {msg.get('session_id', 'N/A')}")
                            if 'references' in msg:
                                print(f"References: {msg['references']}")
                            print("-" * 50)
            else:
                logger.info("No conversations found")
        else:
            logger.error("Failed to save message")
            
    except Exception as e:
        logger.error(f"Error in test_chat_storage: {str(e)}")
        raise

if __name__ == "__main__":
    test_chat_storage()

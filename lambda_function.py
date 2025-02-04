import os
import json
import boto3
import logging
from datetime import datetime, timedelta
from urllib.parse import urlparse

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
service_name = 'bedrock-agent-runtime'
client = boto3.client(service_name)
s3_client = boto3.client('s3')

# Environment variables
knowledgeBaseID = os.environ['KNOWLEDGE_BASE_ID']
# Using Llama 3 8B Instruct model ARN
LLAMA_MODEL_ARN = "arn:aws:bedrock:us-east-1::foundation-model/meta.llama3-8b-instruct"
# Using Titan Text Embeddings V2
TITAN_EMBEDDINGS_ARN = "arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v2"

# Constants
MIN_SCORE_THRESHOLD = 0.7  # Adjust based on testing

def generate_presigned_url(bucket, key, expiration=3600):
    """Generate a presigned URL for an S3 object"""
    try:
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket,
                'Key': key,
                'ResponseContentDisposition': 'inline'
            },
            ExpiresIn=expiration
        )
        return url
    except Exception as e:
        logger.error(f"Error generating presigned URL: {str(e)}")
        return None

def process_s3_urls(references):
    """Convert S3 URIs to presigned URLs in references"""
    processed_refs = []
    for ref in references:
        if 'uri' in ref:
            s3_url = ref['uri']
            parsed_url = urlparse(s3_url)
            bucket = parsed_url.netloc.split('.')[0]
            key = parsed_url.path.lstrip('/')
            presigned_url = generate_presigned_url(bucket, key)
            if presigned_url:
                ref['presigned_url'] = presigned_url
                processed_refs.append(ref)
    return processed_refs

def extract_references(citations):
    """Extract all unique references from citations with score filtering"""
    if not citations:
        logger.warning("No citations received")
        return []
        
    references = []
    seen_uris = set()
    
    for citation in citations:
        if not citation.get('retrievedReferences'):
            continue
            
        for reference in citation.get('retrievedReferences', []):
            # Skip if reference doesn't meet quality criteria
            if (not reference.get('content', {}).get('text', '').strip() or
                reference.get('score', 0) < MIN_SCORE_THRESHOLD):
                continue
                
            if 'location' in reference and 's3Location' in reference['location']:
                uri = reference['location']['s3Location']['uri']
                if uri not in seen_uris:
                    seen_uris.add(uri)
                    snippet = reference.get('content', {}).get('text', '').strip()
                    references.append({
                        'uri': uri,
                        'snippet': snippet,
                        'score': reference.get('score', 0)
                    })
    
    # Sort by relevance score
    references.sort(key=lambda x: x['score'], reverse=True)
    return references

def create_response(status_code, body):
    """Create API Gateway response with CORS headers"""
    return {
        'statusCode': status_code,
        'headers': {
            'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'OPTIONS,POST',
            'Content-Type': 'application/json'
        },
        'body': json.dumps(body)
    }

def preprocess_query(query):
    """Clean and enhance the user query"""
    # Remove extra whitespace
    query = ' '.join(query.split())
    
    # Add context preservation prompt for Llama 3
    query = f"""[INST] Using only the provided knowledge base content, please answer the following question:

{query}

Please ensure your response is factual and based solely on the provided reference materials. [/INST]"""
    
    return query

def get_request_data(event):
    """Extract user query and session ID from the event"""
    try:
        logger.info(f"Received event: {json.dumps(event)}")

        # Handle different event types
        if isinstance(event, dict):
            # API Gateway event
            if 'body' in event:
                if isinstance(event['body'], str):
                    body = json.loads(event['body'])
                else:
                    body = event['body']
            # Direct Lambda invocation
            else:
                body = event
        else:
            raise ValueError("Invalid event format")

        # Extract user query and session ID
        user_query = body.get('user_query')
        session_id = body.get('sessionId')

        return user_query, session_id

    except Exception as e:
        logger.error(f"Error in get_request_data: {str(e)}")
        raise

def lambda_handler(event, context):
    try:
        # Get request data
        user_query, session_id = get_request_data(event)
        logger.info(f"Processing query: {user_query}")
        logger.info(f"Session ID: {session_id}")

        if not user_query:
            return create_response(400, {'error': 'Missing user query'})

        # Preprocess the query
        processed_query = preprocess_query(user_query)

        # Prepare the retrieve request
        retrieve_request = {
            'input': {
                'text': processed_query
            },
            'retrieveAndGenerateConfiguration': {
                'type': 'KNOWLEDGE_BASE',
                'knowledgeBaseConfiguration': {
                    'knowledgeBaseId': knowledgeBaseID,
                    'modelArn': LLAMA_MODEL_ARN,
                    'retrievalConfiguration': {
                        'vectorSearchConfiguration': {
                            'numberOfResults': 10,
                            'overrideSearchType': 'HYBRID',
                            'similarityThreshold': 0.7
                        }
                    },
                    'generationConfiguration': {
                        'temperature': 0.1,  # Lower temperature for Llama 3
                        'topP': 0.9,
                        'maximumLength': 2048,  # Adjusted for Llama 3
                        'stopSequences': ["[/INST]"]  # Llama 3 specific
                    },
                    'embeddingModelArn': TITAN_EMBEDDINGS_ARN  # Specify Titan Embeddings V2
                }
            }
        }

        # Add session ID if available
        if session_id:
            retrieve_request['sessionId'] = session_id

        # Call Bedrock
        response = client.retrieve_and_generate(**retrieve_request)
        
        # Process response
        if 'output' in response and 'text' in response['output']:
            generated_response = response['output']['text']
            # Clean up any remaining [INST] tags from the response
            generated_response = generated_response.replace('[INST]', '').replace('[/INST]', '').strip()
            
            references = extract_references(response.get('citations', []))
            
            logger.info(f"Retrieved references: {json.dumps(references, indent=2)}")
            logger.info(f"Generated response: {generated_response}")

            # Process S3 URLs if references exist
            if references:
                detailed_references = process_s3_urls(references)
            else:
                detailed_references = []

            # Prepare response body
            response_body = {
                'generated_response': generated_response,
                'detailed_references': detailed_references
            }

            # Include session ID in response if present
            if 'sessionId' in response:
                response_body['sessionId'] = response['sessionId']

            return create_response(200, response_body)
        else:
            logger.error("Invalid response format from Bedrock")
            return create_response(500, {'error': 'Invalid response from model'})

    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
        return create_response(500, {'error': str(e)})
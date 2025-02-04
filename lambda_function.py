import os
import json
import boto3
from datetime import datetime, timedelta
from urllib.parse import urlparse

# Initialize AWS clients once outside the handler for better performance
bedrock_agent_runtime = boto3.client('bedrock-agent-runtime')
s3_client = boto3.client('s3')

# Get environment variables
KNOWLEDGE_BASE_ID = os.environ['KNOWLEDGE_BASE_ID']
FOUNDATION_MODEL_ARN = os.environ['FM_ARN']

def create_response(status_code, body):
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

def generate_presigned_url(bucket, key):
    try:
        return s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket,
                'Key': key,
                'ResponseContentDisposition': 'inline'
            },
            ExpiresIn=1800
        )
    except Exception as e:
        print(f"Error generating presigned URL: {str(e)}")
        return None

def process_references(citations):
    """Process citations and return references with presigned URLs"""
    references = []
    seen_uris = set()
    
    for citation in citations:
        for reference in citation.get('retrievedReferences', []):
            location = reference.get('location', {}).get('s3Location', {})
            if not location:
                continue
                
            uri = location.get('uri')
            if not uri or uri in seen_uris:
                continue
                
            seen_uris.add(uri)
            parsed_url = urlparse(uri)
            bucket = parsed_url.netloc.split('.')[0]
            key = parsed_url.path.lstrip('/')
            
            presigned_url = generate_presigned_url(bucket, key)
            if presigned_url:
                references.append({
                    'uri': uri,
                    'presigned_url': presigned_url,
                    'snippet': reference.get('content', {}).get('text', '').strip(),
                    'score': reference.get('score', 0)
                })
    
    return sorted(references, key=lambda x: x['score'], reverse=True)

def get_request_data(event):
    try:
        body = event.get('body')
        if isinstance(body, str):
            body = json.loads(body)
        elif not isinstance(body, dict):
            body = event
            
        return body.get('user_query'), body.get('sessionId')
    except Exception as e:
        print(f"Error parsing request data: {str(e)}")
        raise ValueError("Invalid request format")

def lambda_handler(event, context):
    try:
        # Extract and validate request data
        user_query, session_id = get_request_data(event)
        if not user_query:
            return create_response(400, {'error': 'user_query is required'})

        # Prepare knowledge base request
        retrieve_request = {
            'input': {'text': user_query},
            'retrieveAndGenerateConfiguration': {
                'type': 'KNOWLEDGE_BASE',
                'knowledgeBaseConfiguration': {
                    'knowledgeBaseId': KNOWLEDGE_BASE_ID,
                    'modelArn': FOUNDATION_MODEL_ARN,
                    'retrievalConfiguration': {
                        'vectorSearchConfiguration': {
                            'numberOfResults': 5,
                            'overrideSearchType': 'SEMANTIC'
                        }
                    }
                }
            }
        }

        if session_id:
            retrieve_request['sessionId'] = session_id

        # Get response from knowledge base
        kb_response = bedrock_agent_runtime.retrieve_and_generate(**retrieve_request)
        
        # Process references and get the generated response
        references = process_references(kb_response['citations'])
        generated_response = kb_response['output']['text']
        
        # Create response body
        response_body = {
            'generated_response': generated_response,
            'detailed_references': references,
            'urlExpirationTime': (datetime.utcnow() + timedelta(hours=1)).isoformat(),
            'sessionId': session_id
        }
        
        return create_response(200, response_body)

    except Exception as e:
        print(f"Error in lambda_handler: {str(e)}")
        return create_response(500, {
            'error': str(e),
            'generated_response': 'An error occurred while processing your request.',
            'detailed_references': [],
            'sessionId': session_id if 'session_id' in locals() else None
        })

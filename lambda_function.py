import os
import json
import boto3
from datetime import datetime, timedelta
from urllib.parse import urlparse

# Initialize AWS clients
service_name = 'bedrock-agent-runtime'
client = boto3.client(service_name)
s3_client = boto3.client('s3')

knowledgeBaseID = os.environ['KNOWLEDGE_BASE_ID']
fundation_model_ARN = os.environ['FM_ARN']

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
        print(f"Error generating presigned URL: {str(e)}")
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
    """Extract all unique references from citations"""
    references = []
    seen_uris = set()
    
    for citation in citations:
        for reference in citation.get('retrievedReferences', []):
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
    
    references.sort(key=lambda x: x['score'], reverse=True)
    return references

def create_response(status_code, body):
    """Create API Gateway response with CORS headers"""
    return {
        'statusCode': status_code,
        'headers': {
            'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
            'Access-Control-Allow-Origin': '*',  # Replace with your Streamlit app domain in production
            'Access-Control-Allow-Methods': 'OPTIONS,POST',
            'Content-Type': 'application/json'
        },
        'body': json.dumps(body)
    }

def lambda_handler(event, context):
    try:
        # Handle API Gateway event structure
        if 'body' not in event:
            return create_response(400, {
                'error': 'Missing request body'
            })

        # Parse the request body
        try:
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        except json.JSONDecodeError:
            return create_response(400, {
                'error': 'Invalid JSON in request body'
            })

        # Extract user query and session ID
        user_query = body.get('user_query')
        session_id = body.get('sessionId')

        if not user_query:
            return create_response(400, {
                'error': 'user_query is required in the request body'
            })

        # Prepare the request for Bedrock
        retrieve_request = {
            'input': {
                'text': user_query
            },
            'retrieveAndGenerateConfiguration': {
                'type': 'KNOWLEDGE_BASE',
                'knowledgeBaseConfiguration': {
                    'knowledgeBaseId': knowledgeBaseID,
                    'modelArn': fundation_model_ARN,
                    'retrievalConfiguration': {
                        'vectorSearchConfiguration': {
                            'numberOfResults': 10,
                            'overrideSearchType': 'SEMANTIC'
                        }
                    }
                }
            }
        }

        # Add sessionId if provided
        if session_id:
            retrieve_request['sessionId'] = session_id

        # Call Bedrock
        client_knowledgebase = client.retrieve_and_generate(**retrieve_request)
        
        # Process the response
        references = extract_references(client_knowledgebase['citations'])
        references_with_urls = process_s3_urls(references)
        
        # Get response text and session ID
        generated_response = client_knowledgebase['output']['text']
        new_session_id = client_knowledgebase.get('sessionId')
        
        # Calculate URL expiration time
        expiration_time = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        
        # Create success response
        response_body = {
            'generated_response': generated_response,
            'detailed_references': references_with_urls,
            'urlExpirationTime': expiration_time,
            'sessionId': new_session_id
        }
        
        return create_response(200, response_body)

    except Exception as e:
        print(f"Error: {str(e)}")
        return create_response(500, {
            'error': str(e),
            'generated_response': 'An error occurred while processing your request.',
            'detailed_references': [],
            'sessionId': session_id
        })
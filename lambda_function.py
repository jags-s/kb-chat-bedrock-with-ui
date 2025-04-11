import os
import json
import boto3
from datetime import datetime, timedelta
from urllib.parse import urlparse

# Initialize AWS clients
service_name = 'bedrock-agent-runtime'
client = boto3.client(service_name)
s3_client = boto3.client('s3')

# Create Bedrock client for us-west-2 region to access rerank models
bedrock_runtime_west = boto3.client(
    service_name='bedrock-runtime',
    region_name='us-west-2'
)

knowledgeBaseID = os.environ['KNOWLEDGE_BASE_ID']
fundation_model_ARN = os.environ['FM_ARN']

def generate_presigned_url(bucket, key, expiration=1800):
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

def rerank_references(references, user_query):
    """Rerank references based on relevance using Cohere Rerank 3.5"""
    try:
        # Prepare documents for reranking
        documents = [ref['snippet'] for ref in references]
        
        # Prepare request body for Cohere Rerank
        request_body = {
            "documents": documents,
            "query": user_query,
            "topN": len(documents),
            "returnMetadata": True
        }

        # Call Cohere Rerank model
        response = bedrock_runtime_west.invoke_model(
            modelId="cohere.rerank-3.5",  # or "amazon.rerank-1.0"
            contentType="application/json",
            accept="application/json",
            body=json.dumps(request_body)
        )
        
        # Parse response
        response_body = json.loads(response['body'].read())
        results = response_body.get('results', [])
        
        # Add ranking scores to references
        ranked_references = []
        for idx, result in enumerate(results):
            original_ref = references[result['index']]
            ranked_ref = {
                **original_ref,
                'relevance_score': result['relevance_score'],
                'rank': idx + 1
            }
            ranked_references.append(ranked_ref)
        
        # Sort by relevance score in descending order
        ranked_references.sort(key=lambda x: x['relevance_score'], reverse=True)
        return ranked_references

    except Exception as e:
        print(f"Error in reranking: {str(e)}")
        return references  # Return original references if reranking fails

def extract_references(citations):
    """Extract all references with multiple snippets from citations"""
    references = []
    document_snippets = {}
    
    # First, collect all snippets for each document
    for citation in citations:
        print(f"Processing citation: {json.dumps(citation)}")
        
        for reference in citation.get('retrievedReferences', []):
            print(f"Processing reference: {json.dumps(reference)}")
            
            location = reference.get('location', {})
            s3_location = location.get('s3Location', {})
            
            if s3_location and 'uri' in s3_location:
                uri = s3_location['uri']
                snippet = reference.get('content', {}).get('text', '').strip()
                
                if uri not in document_snippets:
                    document_snippets[uri] = []
                document_snippets[uri].append(snippet)
    
    # Then create references with all snippets
    for uri, snippets in document_snippets.items():
        # Combine snippets (up to 3)
        combined_snippet = ' '.join(snippets[:3])
        references.append({
            'uri': uri,
            'snippet': combined_snippet
        })
    
    return references

def validate_response_relevance(user_query, generated_response, references):
    """Validate if the response has supporting references"""
    print(f"Validating response with {len(references)} references")
    print(f"References: {json.dumps(references)}")
    
    if not references:
        return False, "No supporting references found"
    
    return True, ""

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

def get_request_data(event):
    """Extract user query and session ID from the event"""
    try:
        print(f"Received event: {json.dumps(event)}")

        if isinstance(event, dict):
            if 'body' in event:
                if isinstance(event['body'], str):
                    body = json.loads(event['body'])
                else:
                    body = event['body']
            else:
                body = event
        else:
            raise ValueError("Invalid event format")

        user_query = body.get('user_query')
        session_id = body.get('sessionId')

        return user_query, session_id

    except Exception as e:
        print(f"Error in get_request_data: {str(e)}")
        raise

def lambda_handler(event, context):
    try:
        # Get request data
        try:
            user_query, session_id = get_request_data(event)
        except Exception as e:
            return create_response(400, {
                'error': f'Error processing request: {str(e)}'
            })

        # Validate user query
        if not user_query:
            return create_response(400, {
                'error': 'user_query is required'
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
                            'numberOfResults': 5,
                            'overrideSearchType': 'HYBRID'
                        }
                    },
                    'generationConfiguration': {
                        'promptTemplate': {
                            'textPromptTemplate': """You are a question answering agent. Answer the user's question using the provided search results.
                            
                            IMPORTANT RULES:
                            1. If you cannot find relevant information, say "I apologize, but I don't have enough relevant information to answer this question accurately."
                            2. Only use information from the search results.
                            3. Cite your sources.
                            
                            Search results:
                            $search_results$
                            
                            Question: {input}
                            $output_format_instructions$"""
                        }
                    }
                }
            }
        }

        # Add sessionId if provided
        if session_id:
            retrieve_request['sessionId'] = session_id

        # Call Bedrock and add debug logging
        print(f"Sending request to Bedrock: {json.dumps(retrieve_request)}")
        client_knowledgebase = client.retrieve_and_generate(**retrieve_request)
        print(f"Received response from Bedrock: {json.dumps(client_knowledgebase)}")
        
        # Extract initial references
        references = extract_references(client_knowledgebase['citations'])
        
        # Rerank references based on relevance
        ranked_references = rerank_references(references, user_query)
        
        # Process S3 URLs for ranked references
        references_with_urls = process_s3_urls(ranked_references)
        
        # Get response text and session ID
        generated_response = client_knowledgebase['output']['text']
        new_session_id = client_knowledgebase.get('sessionId')
        
        # Validate response relevance
        is_valid, validation_message = validate_response_relevance(
            user_query, 
            generated_response, 
            references_with_urls
        )
        
        # Prepare response with ranked references
        response_body = {
            'generated_response': generated_response,
            'detailed_references': references_with_urls,
            'urlExpirationTime': (datetime.utcnow() + timedelta(hours=1)).isoformat(),
            'sessionId': new_session_id,
            'sourceCount': len(references_with_urls),
            'validation_status': 'valid' if is_valid else 'warning',
            'validation_message': validation_message if not is_valid else ''
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
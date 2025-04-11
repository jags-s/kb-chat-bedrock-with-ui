import os
import json
import boto3
import logging
from datetime import datetime, timedelta
from urllib.parse import urlparse

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

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
RELEVANCE_THRESHOLD = 0.3  # Configurable threshold for relevance

def generate_presigned_url(bucket, key, expiration=1800):
    """Generate a presigned URL for an S3 object"""
    try:
        logger.info(f"Generating presigned URL for bucket: {bucket}, key: {key}")
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
    logger.info(f"Processing S3 URLs for {len(references)} references")
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
    logger.info(f"Processed {len(processed_refs)} references with presigned URLs")
    return processed_refs

def rerank_references(references, user_query, generated_response):
    """Enhanced reranking with response correlation using Cohere Rerank v3.5"""
    try:
        logger.info(f"Starting reranking process for {len(references)} references")
        documents = [ref['snippet'] for ref in references]
        
        # Prepare request body with exact format required
        request_body = {
            "query": user_query,
            "documents": documents,
            "top_n": len(documents),
            "api_version": 2
        }

        logger.info(f"Rerank request body: {json.dumps(request_body)}")
        
        # Call Cohere Rerank v3.5 model with exact format
        response = bedrock_runtime_west.invoke_model(
            modelId="cohere.rerank-v3-5:0",
            contentType="application/json",
            accept="*/*",
            body=json.dumps(request_body)
        )
        
        response_body = json.loads(response['body'].read())
        logger.info(f"Rerank response: {json.dumps(response_body)}")
        
        # Process results
        results = response_body.get('results', [])
        logger.info(f"Received {len(results)} ranked results")
        
        ranked_references = []
        for idx, result in enumerate(results):
            original_ref = references[result.get('index', 0)]
            relevance_score = result.get('relevance_score', 0)
            
            # Check if reference content is used in response
            is_used = original_ref['snippet'] in generated_response
            
            if relevance_score >= RELEVANCE_THRESHOLD:
                ranked_ref = {
                    **original_ref,
                    'relevance_score': relevance_score,
                    'rank': idx + 1,
                    'used_in_response': is_used
                }
                ranked_references.append(ranked_ref)
                logger.info(f"Reference {idx + 1} - Score: {relevance_score:.3f}, Used: {is_used}")
        
        # Sort by both usage in response and relevance score
        ranked_references.sort(
            key=lambda x: (x['used_in_response'], x['relevance_score']), 
            reverse=True
        )
        
        logger.info(f"Reranking complete. {len(ranked_references)} references above threshold")
        return ranked_references

    except Exception as e:
        logger.error(f"Error in reranking: {str(e)}")
        logger.error(f"Full error details: {str(e.__dict__)}")
        logger.error(f"Request body that caused error: {json.dumps(request_body)}")
        return references

def extract_references(citations, generated_response):
    """Extract references and track which ones were used in the response"""
    logger.info("Starting reference extraction from citations")
    references = []
    document_snippets = {}
    used_citations = set()
    
    for citation in citations:
        logger.debug(f"Processing citation: {json.dumps(citation)}")
        
        for reference in citation.get('retrievedReferences', []):
            logger.debug(f"Processing reference: {json.dumps(reference)}")
            
            location = reference.get('location', {})
            s3_location = location.get('s3Location', {})
            
            if s3_location and 'uri' in s3_location:
                uri = s3_location['uri']
                snippet = reference.get('content', {}).get('text', '').strip()
                
                # More flexible content matching
                if snippet:
                    # Check if any part of the snippet is in the response
                    sentences = snippet.split('.')
                    for sentence in sentences:
                        if sentence.strip() and sentence.strip() in generated_response:
                            used_citations.add(uri)
                            logger.info(f"Found citation used in response: {uri[:50]}...")
                            break
                
                if uri not in document_snippets:
                    document_snippets[uri] = []
                document_snippets[uri].append(snippet)
    
    # Create references with all snippets
    for uri, snippets in document_snippets.items():
        combined_snippet = ' '.join(snippets[:3])
        references.append({
            'uri': uri,
            'snippet': combined_snippet,
            'used_in_response': uri in used_citations
        })
    
    logger.info(f"Extracted {len(references)} references, {len(used_citations)} used in response")
    return references

def validate_response_relevance(user_query, generated_response, references):
    """Enhanced validation of response relevance"""
    logger.info("Starting response relevance validation")
    
    if not references:
        logger.warning("No supporting references found")
        return False, "No supporting references found"
    
    # Check relevance scores
    low_relevance_refs = [
        ref for ref in references 
        if ref.get('relevance_score', 0) < RELEVANCE_THRESHOLD
    ]
    
    if low_relevance_refs:
        logger.warning(f"Found {len(low_relevance_refs)} references with low relevance scores")
        return False, "Some references have low relevance scores"
    
    # Check if response uses reference content
    used_refs = [ref for ref in references if ref.get('used_in_response', False)]
    if not used_refs:
        logger.warning("No references found to be used in the response")
        return False, "Response may not be fully supported by references"
    
    logger.info("Response validation successful")
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
        logger.info(f"Processing event: {json.dumps(event)}")

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

        logger.info(f"Extracted query: {user_query}, sessionId: {session_id}")
        return user_query, session_id

    except Exception as e:
        logger.error(f"Error in get_request_data: {str(e)}")
        raise

def lambda_handler(event, context):
    try:
        # Get request data
        try:
            user_query, session_id = get_request_data(event)
        except Exception as e:
            logger.error(f"Error processing request: {str(e)}")
            return create_response(400, {
                'error': f'Error processing request: {str(e)}'
            })

        # Validate user query
        if not user_query:
            logger.error("Missing user query")
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

        if session_id:
            retrieve_request['sessionId'] = session_id

        # Call Bedrock
        logger.info(f"Sending request to Bedrock: {json.dumps(retrieve_request)}")
        client_knowledgebase = client.retrieve_and_generate(**retrieve_request)
        logger.info("Received response from Bedrock")
        
        # Get response text first
        generated_response = client_knowledgebase['output']['text']
        logger.info(f"Generated response: {generated_response[:200]}...")
        
        # Extract and process references
        references = extract_references(
            client_knowledgebase['citations'], 
            generated_response
        )
        
        # Rerank references
        ranked_references = rerank_references(
            references, 
            user_query, 
            generated_response
        )
        
        # Filter relevant references
        relevant_references = [
            ref for ref in ranked_references 
            if ref.get('relevance_score', 0) >= RELEVANCE_THRESHOLD
        ]
        
        # Process S3 URLs
        references_with_urls = process_s3_urls(relevant_references)
        
        # Validate response
        is_valid, validation_message = validate_response_relevance(
            user_query, 
            generated_response, 
            references_with_urls
        )
        
        # Prepare debug information
        debug_info = {
            'query': user_query,
            'total_references': len(references),
            'relevant_references': len(relevant_references),
            'relevance_scores': [
                {
                    'score': ref.get('relevance_score', 0),
                    'used': ref.get('used_in_response', False)
                }
                for ref in references_with_urls
            ],
            'used_references': len([
                ref for ref in references_with_urls 
                if ref.get('used_in_response', False)
            ])
        }
        
        # Prepare response
        response_body = {
            'generated_response': generated_response,
            'detailed_references': references_with_urls,
            'urlExpirationTime': (datetime.utcnow() + timedelta(hours=1)).isoformat(),
            'sessionId': client_knowledgebase.get('sessionId'),
            'sourceCount': len(references_with_urls),
            'validation_status': 'valid' if is_valid else 'warning',
            'validation_message': validation_message if not is_valid else '',
            'debug_info': debug_info
        }
        
        logger.info(f"Returning response with {len(references_with_urls)} references")
        return create_response(200, response_body)

    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
        return create_response(500, {
            'error': str(e),
            'generated_response': 'An error occurred while processing your request.',
            'detailed_references': [],
            'sessionId': session_id if 'session_id' in locals() else None
        })

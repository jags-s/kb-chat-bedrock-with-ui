# 1. Import libraries
import os
import json
import boto3

# 2. Knowledge base - Foundation Model & Client SetUp
service_name = 'bedrock-agent-runtime'
client = boto3.client(service_name)

knowledgeBaseID = os.environ['KNOWLEDGE_BASE_ID']
fundation_model_ARN = os.environ['FM_ARN']

def extract_references(citations):
    """
    Extract all unique references from citations
    Returns a list of dictionaries containing reference details
    """
    references = []
    seen_uris = set()  # To track unique URIs
    
    for citation in citations:
        for reference in citation.get('retrievedReferences', []):
            if 'location' in reference and 's3Location' in reference['location']:
                uri = reference['location']['s3Location']['uri']
                if uri not in seen_uris:
                    seen_uris.add(uri)
                    
                    # Extract snippet if available
                    snippet = reference.get('content', {}).get('text', '').strip()
                    
                    references.append({
                        'uri': uri,
                        'snippet': snippet,
                        'score': reference.get('score', 0)
                    })
    
    # Sort references by score if available
    references.sort(key=lambda x: x['score'], reverse=True)
    return references

def lambda_handler(event, context):
    try:
        # 3.1. Retrieve User query/Question  
        user_query = event['user_query']
        
        # 3.2. API Call to "retrieve_and_generate" function
        client_knowledgebase = client.retrieve_and_generate(
            input={
                'text': user_query
            },
            retrieveAndGenerateConfiguration={
                'type': 'KNOWLEDGE_BASE',
                'knowledgeBaseConfiguration': {
                    'knowledgeBaseId': knowledgeBaseID,
                    'modelArn': fundation_model_ARN,
                    'retrievalConfiguration': {
                        'vectorSearchConfiguration': {
                            'numberOfResults': 10  # Increase number of results
                        }
                    }
                }
            }
        )
                
        # 3.3. Process all citations and references
        print("----------- Reference Details -------------")
        
        # Extract all references
        references = extract_references(client_knowledgebase['citations'])
        
        # Get the generated response
        generated_response = client_knowledgebase['output']['text']
        
        # Create a list of S3 URIs for all references
        s3_locations = [ref['uri'] for ref in references]
        
        # 3.4 Final object to return
        final_result = {
            'statusCode': 200,
            'query': user_query,
            'generated_response': generated_response,
            's3_location': ','.join(s3_locations),  # Join all URIs with comma for backward compatibility
            'detailed_references': references  # Include detailed reference information
        }
        
        # 3.5 Print & Return result
        print("Result details:\n", json.dumps(final_result, indent=2))
        
        return final_result
        
    except Exception as e:
        error_response = {
            'statusCode': 500,
            'query': event.get('user_query', ''),
            'error': str(e),
            'generated_response': 'An error occurred while processing your request.',
            's3_location': 'N/A',
            'detailed_references': []
        }
        print("Error:", str(e))
        return error_response

import azure.functions as func
import logging
import os
from azure.ai.inference import EmbeddingsClient
from azure.core.credentials import AzureKeyCredential
import json

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

@app.route(route="embed_trigger")
def embed_trigger(req: func.HttpRequest) -> func.HttpResponse:
    embeddings_client = None
    endpoint=os.environ["AZURE_AI_EMBEDDINGS_ENDPOINT"]
    credential=AzureKeyCredential(os.environ["AZURE_AI_EMBEDDINGS_KEY"])
    if "openai" in endpoint:
        embeddings_client = EmbeddingsClient(
            endpoint=endpoint,
            credential=credential,
            api_version=os.environ["AZURE_AI_EMBEDDINGS_API_VERSION"]
        )
    else:
        embeddings_client = EmbeddingsClient(
            endpoint=endpoint,
            credential=credential
        )
    logging.info('Python HTTP trigger function processed a request.')
    
    values = req.get_json()['values']
    results = []
    for value in values:
        result = {}
        result['recordId'] = value['recordId']
        data = value['data']
        if "text" in data:
            logging.info("Text vectorization")
            resp_text = embeddings_client.embed(input=[data['text']])
            result['data'] = {}
            result['data']["vector"] = resp_text.data[0]["embedding"]
            results.append(result)
        elif "imageUrl" in data:
            logging.info("Image URL vectorization")
        elif "imageBinary" in data:
            logging.info("Image binary vectorization")
        else:
            print("Invalid data")
    resp = {}
    resp['values'] = results
    return func.HttpResponse(json.dumps(resp), mimetype="application/json")
        
    
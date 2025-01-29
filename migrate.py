from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.core.credentials import AzureKeyCredential
import os
from azure.search.documents import SearchClient  
from azure.search.documents.indexes import SearchIndexClient
import tqdm  
import time
from azure.search.documents.indexes.models import (
    VectorSearch,
    SearchIndex,
)
import json
from azure.ai.inference import EmbeddingsClient

load_dotenv("credentials.env") #, override=True) # take environment variables from .env.

# Variables not used here do not need to be updated in your .env file
source_endpoint = os.environ["AZURE_SEARCH_SERVICE_ENDPOINT"]
source_credential = AzureKeyCredential(os.environ["AZURE_SEARCH_ADMIN_KEY"]) if len(os.environ["AZURE_SEARCH_ADMIN_KEY"]) > 0 else DefaultAzureCredential()
source_index_name = os.environ["AZURE_SEARCH_INDEX"]
# Default to same service for copying index
target_endpoint = os.environ["AZURE_TARGET_SEARCH_SERVICE_ENDPOINT"] if len(os.environ["AZURE_TARGET_SEARCH_SERVICE_ENDPOINT"]) > 0 else source_endpoint
target_credential = AzureKeyCredential(os.environ["AZURE_TARGET_SEARCH_ADMIN_KEY"]) if len(os.environ["AZURE_TARGET_SEARCH_ADMIN_KEY"]) > 0 else DefaultAzureCredential()
target_index_name = os.environ["AZURE_TARGET_SEARCH_INDEX"]

def initialize_embedding_model():
    embeddings_client = None
    if "openai" in os.environ["AZURE_AI_EMBEDDINGS_ENDPOINT"]:
        print("initializing embeddings client AOAI")
        embeddings_client = EmbeddingsClient(
            endpoint=os.environ["AZURE_AI_EMBEDDINGS_ENDPOINT"],
            credential=AzureKeyCredential(os.environ["AZURE_AI_EMBEDDINGS_KEY"]),
            api_version=os.environ["AZURE_AI_EMBEDDINGS_API_VERSION"]
        )
    else:
        print("initializing embeddings client not AOAI")
        embeddings_client = EmbeddingsClient(
            endpoint=os.environ["AZURE_AI_EMBEDDINGS_ENDPOINT"],
            credential=AzureKeyCredential(os.environ["AZURE_AI_EMBEDDINGS_KEY"])
        )
    return embeddings_client

def get_embedding(embeddings_model, text):
    response = embeddings_model.embed(input=[text])
    return response.data[0]["embedding"]

def create_clients(endpoint, credential, index_name):  
    search_client = SearchClient(endpoint=endpoint, index_name=index_name, credential=credential)  
    index_client = SearchIndexClient(endpoint=endpoint, credential=credential)  
    return search_client, index_client

def total_count(search_client):
    response = search_client.search(include_total_count=True, search_text="*", top=0)
    return response.get_count()
  
def search_results_with_filter(search_client, key_field_name):
    last_item = None
    response = search_client.search(search_text="*", top=100000, order_by=key_field_name).by_page()
    while True:
        for page in response:
            page = list(page)
            if len(page) > 0:
                last_item = page[-1]
                yield page
            else:
                last_item = None
        
        if last_item:
            response = search_client.search(search_text="*", top=100000, order_by=key_field_name, filter=f"{key_field_name} gt '{last_item[key_field_name]}'").by_page()
        else:
            break

def search_results_without_filter(search_client):
    response = search_client.search(search_text="*", top=100000).by_page()
    for page in response:
        page = list(page)
        yield page

def add_api_key(vectors):
    vectorizers = []
    for vectorizer in vectors["vectorizers"]:
        if vectorizer["kind"] == "azureOpenAI":
            vectorizer["azureOpenAIParameters"]["apiKey"] = os.environ["azureOpenAI_API_KEY"]
        elif vectorizer["kind"] == "customWebApi":
            vectorizer["customWebApiParameters"]["httpHeaders"]["x-functions-key"] = os.environ["customWebApi_API_KEY"]
        vectorizers.append(vectorizer)
    vectors["vectorizers"] = vectorizers
    return vectors

def backup_and_restore_index(source_endpoint, source_key, source_index_name, target_endpoint, target_key, target_index_name):  
    # Create search and index clients  
    source_search_client, source_index_client = create_clients(source_endpoint, source_key, source_index_name)  
    target_search_client, target_index_client = create_clients(target_endpoint, target_key, target_index_name)

    # Load target vector profiles
    vectors = json.load(open("vectors.json"))
    vectors = add_api_key(vectors)
    vector_search = VectorSearch.from_dict(vectors)

    # Load json file for column mapping to vector
    vector_mapping = json.load(open("vector_mapping.json"))
    embeddings_model = initialize_embedding_model()
  
    # Get the source index definition  
    source_index = source_index_client.get_index(name=source_index_name)
    target_fields = []
    non_retrievable_fields = []
    for field in source_index.fields:
        if field.hidden == True:
            non_retrievable_fields.append(field)
        if field.key == True:
            key_field = field
        if field.vector_search_dimensions is not None:
            for key in vector_mapping:
                if key["target"] == field.name:
                    field.vector_search_dimensions = key["vector_length"]
        target_fields.append(field)

    if not key_field:
        raise Exception("Key Field Not Found")
    
    if len(non_retrievable_fields) > 0:
        print(f"WARNING: The following fields are not marked as retrievable and cannot be backed up and restored: {', '.join(f.name for f in non_retrievable_fields)}")
  
    # Create target index with the same definition 
    # source_index.name = target_index_name
    target_index = SearchIndex(name=target_index_name, fields=target_fields, vector_search=vector_search, semantic_search=source_index.semantic_search)
    target_index_client.create_or_update_index(target_index)
  
    document_count = total_count(source_search_client)
    can_use_filter = key_field.sortable and key_field.filterable
    if not can_use_filter:
        print("WARNING: The key field is not filterable or not sortable. A maximum of 100,000 records can be backed up and restored.")
    # Backup and restore documents  
    all_documents = search_results_with_filter(source_search_client, key_field.name) if can_use_filter else search_results_without_filter(source_search_client)

    print("Backing up and restoring documents:")  
    failed_documents = 0  
    failed_keys = []  
    with tqdm.tqdm(total=document_count) as progress_bar:  
        for page in all_documents:
            new_page=[]
            for document in page:
                for key in vector_mapping:
                    source = key["source"]
                    embedding_text = get_embedding(embeddings_model, document[source])
                    document[key["target"]] = embedding_text
                new_page.append(document)
                # print(document)
            result = target_search_client.upload_documents(documents=new_page)  
            progress_bar.update(len(result))  

            for item in result:  
                if item.succeeded is not True:  
                    failed_documents += 1
                    failed_keys.append(page[result.index_of(item)].id)  
                    print(f"Document upload error: {item.error.message}")  
  
    if failed_documents > 0:  
        print(f"Failed documents: {failed_documents}")  
        print(f"Failed document keys: {failed_keys}")  
    else:  
        print("All documents uploaded successfully.")  
  
    print(f"Successfully backed up '{source_index_name}' and restored to '{target_index_name}'")  
    return source_search_client, target_search_client, all_documents  


def verify_counts(source_search_client, target_search_client):  
    source_document_count = source_search_client.get_document_count()
    time.sleep(10)  
    target_document_count = target_search_client.get_document_count()  
  
    print(f"Source document count: {source_document_count}")  
    print(f"Target document count: {target_document_count}")  
  
    if source_document_count == target_document_count:  
        print("Document counts match.")  
    else:  
        print("Document counts do not match.") 


if __name__ == "__main__":
    print("Starting migration script")
    source_search_client, target_search_client, all_documents = backup_and_restore_index(source_endpoint, source_credential, source_index_name, target_endpoint, target_credential, target_index_name)
    # Call the verify_counts function with the search_clients returned by the backup_and_restore_index function  
    verify_counts(source_search_client, target_search_client)
    print("Migration script completed")
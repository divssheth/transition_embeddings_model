# Transitioning AI Search Index: A guide to migrating between embeddings models

Organizations have used embedding models to increase performance of their Azure AI Search. As all models, even the embeddings models get updated. Currently, upgrading the embeddings model is not straight-forward process, it involves re-indexing the entire dataset.

Having a process to seamlessly replace the embeddings model within AI Search is important for several reasons:

1. **Adaptability**: As new and more efficient embeddings models are developed, a seamless transition process allows organizations to quickly adapt and integrate these advancements, ensuring that search capabilities remain cutting-edge.
2. **Performance Optimization**: Different embeddings models may offer better performance in terms of accuracy, speed, or resource efficiency. The ability to switch models without disruption allows for continuous optimization of the search system.
3. **Flexibility**: A flexible process supports experimentation with various models to determine which best meets specific business needs or use cases, without the risk of downtime or significant operational overhead.
4. **Cost Efficiency**: Seamless model replacement can reduce costs associated with retraining and reindexing, as well as minimize potential revenue loss from interrupted services.
5. **Consistency and Reliability**: Ensuring a consistent and reliable search experience for users is crucial. A robust replacement process minimizes potential disruptions, maintaining user trust and satisfaction.

Overall, such a process enhances the longevity and adaptability of AI Search systems in rapidly evolving technological landscapes.

This code repository help you move the existing index to a new index with the updated embeddings model, it keeps all the configuration same as the source updating only the vector profile.

### Steps to execute the code:
The code base makes use of the Azure AI model inference SDK that allows you to switch the embeddings model without the need to change the code.

1. Create a `credentials.env` file and fill in the details. See `.credentials.env` file for example
2. Create a `vector_mapping.json` file, sample provided. This file is used to map the source fields to vector fields.
The vector mapping file is used to list all the fields and their corresponding vector fields along with the new vector size.
`source` - name of the field whose vector representation is to be stored
`target` - name of the field where the vector representation is stored
`vector_length` - length of the vector representation of the field

3. Create a `vectors.json` - this file is the updated vector profile for the target_index. Sample provided. Further details here - https://learn.microsoft.com/en-us/azure/search/vector-search-how-to-configure-vectorizer#define-a-vectorizer-and-vector-profile

4. Run the code

**Additional Steps**:
Post successful execution, please create an indexer to update the target_index on a scheduled basis.

**Limitations**:
1. Code only works with API_KEY for now and does not support USER/SYSTEM assigned identity
2. It is tested with AOAI embedding models i.e. embeddings-002, embeddings-large
3. Supports upto 100K records in the Search index

**Future scope**:
1. Test with open source embedding models hosted in Azure AI Foundry using Custom api
2. Test Indexer functionality by pointing it to the new target_index

## Credits:
Backup and Restore example - https://github.com/Azure/azure-search-vector-samples/blob/main/demo-python/code/index-backup-restore/azure-search-backup-and-restore.ipynb

Integrated Vectorization - https://github.com/Azure/azure-search-vector-samples/blob/main/demo-python/code/integrated-vectorization/azure-search-integrated-vectorization-sample.ipynb
import chromadb
from chromadb.utils import embedding_functions
import uuid


class SemanticCache:
    def __init__(self, threshold=0.90):
        # Initialize an in-memory vector database client
        self.chroma_client = chromadb.Client()
        # Load a built-in, lightweight embedding model to convert text to vectors
        self.embedding_fn = embedding_functions.DefaultEmbeddingFunction()
        self.collection = self.chroma_client.get_or_create_collection(
            name="voice_agent_cache",
            embedding_function=self.embedding_fn
        )
        self.threshold = threshold

    def check_cache(self, query: str):
        """Queries the vector DB. Returns a cached answer if similarity matches."""
        results = self.collection.query(
            query_texts=[query],
            n_results=1,
            include=["documents", "distances"]
        )
        if results and results['documents'] and results['documents'][0]:
            distance = results['distances'][0][0]
            similarity = 1 - distance
            # If the calculated similarity is equal to or greater than our threshold
            if similarity >= self.threshold:
                return results['documents'][0][0]
        return None

    def add_to_cache(self, query: str, response: str):
        """Saves a new user query and text response pair into the vector DB."""
        self.collection.add(
            documents=[response],
            metadatas=[{"query": query}],
            ids=[str(uuid.uuid4())]
        )

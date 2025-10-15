from chromadb import Client

def get_chroma_client():
    """Restituisce un client Chroma locale aggiornato"""
    client = Client()  # senza parametri
    return client

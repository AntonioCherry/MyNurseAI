from app.database.chromadb import get_chroma_client

def test_chroma_local():
    client = get_chroma_client()
    print("✅ Chroma locale connesso!")

    # Creiamo una collezione di test
    collection = client.get_or_create_collection(name="test_collection")

    # Aggiungiamo un documento
    collection.add(
        ids=["doc1"],
        documents=["Questo è un documento medico di esempio."],
        metadatas=[{"type": "test"}]
    )

    # Cerchiamo nel DB
    results = collection.query(query_texts=["documento medico"], n_results=1)
    print("🔍 Risultato query:", results)

if __name__ == "__main__":
    test_chroma_local()

import sys
import os
import pathlib
import logging

chatbot_dir = str(pathlib.Path(__file__).parent / "chatbot")
if chatbot_dir not in sys.path:
    sys.path.insert(0, chatbot_dir)

from chatbot.database.vector_store import build_or_load_store
from chatbot.utils.document_loaders import read_txt
from chatbot.utils.text_processing import chunk_text, get_year_from_filename, get_law_base_name
from qdrant_client.models import PointStruct
from pyvi import ViTokenizer
from rank_bm25 import BM25Okapi

logging.basicConfig(level=logging.INFO)

def main():
    print("Loading existing index...")
    store = build_or_load_store()
    
    file_path = pathlib.Path(chatbot_dir) / "data_laws" / "sme_huong_dan_thanh_lap_ho_tro.txt"
    print(f"Fast updating index with: {file_path}")
    
    text = read_txt(file_path)
    if not text:
        print("Failed to read text.")
        return
        
    law_name = file_path.stem
    chunk_dicts = chunk_text(text, law_name)
    year = get_year_from_filename(file_path.name)
    law_base = get_law_base_name(file_path.name)
    
    new_chunks = []
    new_meta = []
    offset = len(store.corpus_chunks)
    
    for i, cd in enumerate(chunk_dicts):
        # Skip LLM entity extraction to save API limits
        entities = ""
        bm25_input = cd["text"]
        new_chunks.append(cd["text"])
        new_meta.append({
            "source_file": file_path.name, "book": cd["book"], "chapter": cd.get("chapter", ""),
            "section": cd.get("section", ""), "article": cd.get("article", ""),
            "prev_title": cd.get("prev_title", ""), "next_title": cd.get("next_title", ""),
            "chunk_id": offset + i, "entities": entities, "year": year, "law_base": law_base,
            "bm25_input": bm25_input
        })
        
    if not new_chunks:
        print("No chunks generated.")
        return
        
    embeddings = store.embedder.encode(new_chunks, convert_to_numpy=True, normalize_embeddings=True)
    if store.client is None:
        print("No Qdrant client.")
        return
        
    store._ensure_collection()
    
    points = []
    for i, (chunk, meta) in enumerate(zip(new_chunks, new_meta)):
        points.append(PointStruct(
            id=offset + i,
            vector=embeddings[i].tolist(),
            payload={"text": chunk, **meta}
        ))
    
    # Check if Qdrant is connected
    from chatbot.config import QDRANT_COLLECTION
    try:
        store.client.upsert(collection_name=QDRANT_COLLECTION, points=points)
    except Exception as e:
        print(f"Error upserting to Qdrant: {e}")
    
    store.corpus_chunks.extend(new_chunks)
    store.corpus_meta.extend(new_meta)
    
    tokenized_corpus = [ViTokenizer.tokenize(meta["bm25_input"]).split() for meta in store.corpus_meta]
    store.bm25 = BM25Okapi(tokenized_corpus)
    
    store.save()
    print(f"Successfully updated index (Fast Mode) for: {file_path.name}")

if __name__ == "__main__":
    main()

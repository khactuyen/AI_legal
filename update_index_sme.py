import sys
import os
import pathlib
import logging

chatbot_dir = str(pathlib.Path(__file__).parent / "chatbot")
if chatbot_dir not in sys.path:
    sys.path.insert(0, chatbot_dir)

from chatbot.database.vector_store import build_or_load_store

# Set up logging
logging.basicConfig(level=logging.INFO)

def main():
    print("Loading existing index...")
    store = build_or_load_store()
    
    file_path = pathlib.Path(chatbot_dir) / "data_laws" / "sme_huong_dan_thanh_lap_ho_tro.txt"
    print(f"Updating index with: {file_path}")
    
    if store.update_index(file_path):
        print("Successfully updated index!")
    else:
        print("Failed to update index.")

if __name__ == "__main__":
    main()

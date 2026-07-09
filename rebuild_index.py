import sys
import os
import pathlib
import logging

chatbot_dir = str(pathlib.Path(__file__).parent / "chatbot")
if chatbot_dir not in sys.path:
    sys.path.insert(0, chatbot_dir)

from chatbot.database.vector_store import build_or_load_store

logging.basicConfig(level=logging.INFO)

def main():
    print("Forcing rebuild of index...")
    store = build_or_load_store()
    print("Rebuild completed.")

if __name__ == "__main__":
    main()

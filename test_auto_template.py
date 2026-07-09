import sys
import os
import asyncio
import json
import pathlib

chatbot_dir = str(pathlib.Path(__file__).parent / "chatbot")
if chatbot_dir not in sys.path:
    sys.path.insert(0, chatbot_dir)

from chatbot.services.llm_service import process_user_message_stream
from chatbot.database.vector_store import build_or_load_store

async def test_auto_template():
    print("Loading vector store...")
    store = build_or_load_store()
    
    print("Testing auto template generation...")
    # Simulate a conversation where the user provides all info
    msg = "Soạn cho tôi hợp đồng lao động thời vụ. Tên công ty: Công ty ABC. Tên người lao động: Nguyễn Văn A. Mã số thuế: 123456789. Địa chỉ: Hà Nội."
    
    for chunk in process_user_message_stream(store, msg):
        try:
            data = json.loads(chunk)
            if data["type"] == "content":
                print(data["text"], end="")
            elif data["type"] == "status":
                print(f"\n[STATUS] {data['text']}\n")
        except:
            print(chunk, end="")

if __name__ == "__main__":
    asyncio.run(test_auto_template())

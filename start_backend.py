import uvicorn
import os

if __name__ == "__main__":
    os.chdir(r"d:\Project Save\chatbot law")
    uvicorn.run("chatbot.api:app", host="0.0.0.0", port=8000, reload=True)

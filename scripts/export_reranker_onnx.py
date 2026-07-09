"""
Script xuất mô hình Reranker sang định dạng ONNX để tăng tốc độ inference trên CPU.
Chạy một lần duy nhất: python scripts/export_reranker_onnx.py
"""

import os
import sys
import pathlib
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

# Cấu hình
MODEL_NAME = "BAAI/bge-reranker-base"
OUTPUT_DIR = pathlib.Path(__file__).parent.parent / "chatbot" / "index_laws"
OUTPUT_PATH = OUTPUT_DIR / "reranker.onnx"

def export_to_onnx():
    print(f"[1/4] Loading model: {MODEL_NAME}...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
    model.eval()

    print(f"[2/4] Preparing dummy input...")
    dummy_input = tokenizer(
        "Sample legal question",
        "Article 15 of Enterprise Law 2020",
        return_tensors="pt",
        max_length=512,
        padding="max_length",
        truncation=True,
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[3/4] Exporting to ONNX: {OUTPUT_PATH}...")
    torch.onnx.export(
        model,
        (dummy_input["input_ids"], dummy_input["attention_mask"]),
        str(OUTPUT_PATH),
        input_names=["input_ids", "attention_mask"],
        output_names=["logits"],
        dynamic_axes={
            "input_ids": {0: "batch_size", 1: "sequence_length"},
            "attention_mask": {0: "batch_size", 1: "sequence_length"},
            "logits": {0: "batch_size"},
        },
        opset_version=14,
    )

    # Save tokenizer to the same directory
    tokenizer_dir = OUTPUT_DIR / "reranker_tokenizer"
    tokenizer.save_pretrained(str(tokenizer_dir))

    print(f"[4/4] Completed successfully!")
    print(f"  - ONNX model: {OUTPUT_PATH}")
    print(f"  - Tokenizer: {tokenizer_dir}")
    print(f"  - File size: {OUTPUT_PATH.stat().st_size / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    export_to_onnx()

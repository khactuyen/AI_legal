import os
import shutil

base_dir = r"d:\Project Save\Drowssiness"
train_dir = os.path.join(base_dir, "Train")

# Create new structure
dirs_to_create = ["notebooks", "models", "assets", "web_app"]
for d in dirs_to_create:
    os.makedirs(os.path.join(base_dir, d), exist_ok=True)

# Move files
moves = [
    (os.path.join(train_dir, "DATA PREPROCESSING .ipynb"), os.path.join(base_dir, "notebooks")),
    (os.path.join(train_dir, "Train.ipynb"), os.path.join(base_dir, "notebooks")),
    (os.path.join(train_dir, "best_model.pth"), os.path.join(base_dir, "models")),
    (os.path.join(train_dir, "confusion_matrix.png"), os.path.join(base_dir, "assets")),
    (os.path.join(train_dir, "model_flow_diagram.png"), os.path.join(base_dir, "assets")),
    (os.path.join(train_dir, "training_history.png"), os.path.join(base_dir, "assets")),
    (os.path.join(train_dir, "test_drowsy.mp4"), os.path.join(base_dir, "assets")),
    (os.path.join(train_dir, "test_nondrowsy.mp4"), os.path.join(base_dir, "assets")),
    (os.path.join(train_dir, "requirements.txt"), base_dir),
]

for src, dst in moves:
    if os.path.exists(src):
        shutil.move(src, dst)

# Move web_demo contents
web_demo_dir = os.path.join(train_dir, "web_demo")
web_app_dir = os.path.join(base_dir, "web_app")
if os.path.exists(web_demo_dir):
    for item in os.listdir(web_demo_dir):
        shutil.move(os.path.join(web_demo_dir, item), web_app_dir)

# Update model path in model.py
model_py_path = os.path.join(web_app_dir, "model.py")
if os.path.exists(model_py_path):
    with open(model_py_path, "r", encoding="utf-8") as f:
        content = f.read()
    content = content.replace("MODEL_PATH = '../best_model.pth'", "MODEL_PATH = '../models/best_model.pth'")
    with open(model_py_path, "w", encoding="utf-8") as f:
        f.write(content)

# Clean up empty directories
shutil.rmtree(web_demo_dir, ignore_errors=True)
shutil.rmtree(train_dir, ignore_errors=True)

print("Project restructured successfully!")

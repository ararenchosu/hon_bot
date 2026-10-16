import json
import os

DATA_FILE = "kn_points_data.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_points(user_id: int):
    data = load_data()
    return data.get(str(user_id), 0)

def add_points(user_id: int, amount: int):
    data = load_data()
    uid = str(user_id)
    data[uid] = data.get(uid, 0) + amount
    save_data(data)

def set_points(user_id: int, amount: int):
    data = load_data()
    data[str(user_id)] = amount
    save_data(data)

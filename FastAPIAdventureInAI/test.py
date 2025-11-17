import requests

def test_generate_story():
    url = "http://localhost:9000/generate_story/"
    payload = {
        "context": {
            "NarratorDirectives": "Test directive",
            "UniverseName": "Test World",
            "UniverseTokens": "test tokens",
            "StoryPreface": "Test preface",
            "GameSettings": {"Rating": "G", "StorySplitter": "---END---"},
            "PlayerInfo": {"Name": "Tester", "Gender": "M"},
            "TokenizedHistory": [],
            "RecentStory": ["The hero awoke.", "He found a sword."],
            "FullHistory": ["The hero awoke.", "He found a sword."],
            "CurrentAction": "Look around"
        },
        "user_input": "Look around",
        "include_initial": False
    }
    response = requests.post(url, json=payload)
    print("generate_story response:", response.json())

def test_summarize_chunk():
    url = "http://localhost:9000/summarize_chunk/"
    payload = {
        "chunk": ["The hero awoke.", "He found a sword.", "He left the house."],
        "max_tokens": 50
    }
    response = requests.post(url, json=payload)
    print("summarize_chunk response:", response.json())

if __name__ == "__main__":
    test_generate_story()
    test_summarize_chunk()

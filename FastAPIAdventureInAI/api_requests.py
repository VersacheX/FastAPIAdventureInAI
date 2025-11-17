import requests
import os
API_SERVER_URL = os.environ.get("API_SERVER_URL", "http://localhost:8000")
from aiadventureinpythonconstants import TOKENIZE_HISTORY_CHUNK_SIZE
from dtos import UserDTO, SavedGameDTO
import json
# Removed unused import: get_current_chapter_section
from converters import serialize_for_json

def login_user(username, password):
    url = f"{API_SERVER_URL}/token"
    data = {"username": username, "password": password}
    response = requests.post(url, data=data)
    if response.status_code == 200:
        token = response.json()["access_token"]
        user_resp = requests.get(
            f"{API_SERVER_URL}/users/by_username/{username}",
            headers={"Authorization": f"Bearer {token}"}
        )
        if user_resp.status_code == 200:
            user = user_resp.json()
            user_dto = UserDTO.model_validate(user)
            return token, user_dto
        else:
            raise Exception("Failed to fetch user info after login.")
    else:
        error_msg = response.json().get("detail", response.text)
        raise Exception(f"Login failed: {error_msg}")

def load_game(token, user):
    user_id = user.id
    url = f"{API_SERVER_URL}/users/{user_id}/saved_games/"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print("Failed to fetch saved games:", response.json().get("detail", response.text))
        return None
    games = [SavedGameDTO.model_validate(game) for game in response.json()]
    if not games:
        print("No saved games found for this user.")
        return None
    print("\nSaved Games:")
    for idx, game in enumerate(games, 1):
        # Use history_count to get chapter, section, subsection
        chapter, section, subsection = get_current_chapter_section(
            [None] * game.history_count,  # simulate history list of correct length
            [None] * (game.history_count // TOKENIZE_HISTORY_CHUNK_SIZE)   # simulate tokenized history list
        )
        print(
            f"{idx}. {game.player_name} ({game.created_at}) - "
            f"{game.world_name} | {game.rating_name} | "
            f"Ch {chapter}.{section}.{subsection}"
        )
    while True:
        choice = input(f"Select a game to load (1-{len(games)}), or 0 to cancel: ").strip()
        if choice == "0":
            return None
        try:
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(games):
                selected_game = games[choice_idx]
                print(f"Loaded game: {selected_game.player_name}")
                # Fetch full game details by ID
                game_detail_url = f"{API_SERVER_URL}/saved_games/{selected_game.id}"
                detail_resp = requests.get(game_detail_url, headers=headers)
                if detail_resp.status_code == 200:
                    full_game = SavedGameDTO.model_validate(detail_resp.json())
                    return full_game
                else:
                    print("Failed to load full game details:", detail_resp.json().get("detail", detail_resp.text))
                    return None
            else:
                print("Invalid selection.")
        except ValueError:
            print("Please enter a valid number.")

def save_game(context, token, user_id, world_id, rating_id, game_id=None):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    history_payload = [
        {"entry": entry} for entry in context['history']
    ]
    tokenized_history_payload = [
        {
            "start_index": block.get("start_index", 0),
            "end_index": block.get("end_index", 0),
            "summary": block.get("summary", "")
        }
        for block in context.get("tokenized_history", [])
    ]
    payload = {
        "user_id": int(user_id),
        "world_id": int(world_id),
        "rating_id": int(rating_id),
        "player_name": context['player_name'],
        "player_gender": context['player_gender'],
        "history": history_payload,
        "tokenized_history": tokenized_history_payload
    }
    if game_id:
        url = f"{API_SERVER_URL}/saved_games/{game_id}"
        response = requests.put(url, headers=headers, data=json.dumps(serialize_for_json(payload)))
    else:
        url = f"{API_SERVER_URL}/saved_games/"
        response = requests.post(url, headers=headers, data=json.dumps(serialize_for_json(payload)))
        if response.status_code in (200, 201):
            returned = response.json()
            context['game_id'] = returned.get('id')
            return context['game_id']
    if response.status_code in (200, 201):
        if game_id:
            returned = response.json()
            context['game_id'] = returned.get('id', game_id)
        return context['game_id']
    else:
        error_msg = response.json().get("detail", response.text)
        raise Exception(f"Auto-save failed: {error_msg}")

def save_new_history_entry(token, game_id, entry):
    url = f"{API_SERVER_URL}/history/?saved_game_id={game_id}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"entry": entry}
    response = requests.post(url, headers=headers, data=json.dumps(serialize_for_json(payload)))
    if not response.status_code in (200, 201):
        raise Exception("Failed to save history entry.")

def save_new_tokenized_history(token, game_id, block):
    url = f"{API_SERVER_URL}/tokenized_history/?saved_game_id={game_id}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "start_index": block.get("start_index", 0),
        "end_index": block.get("end_index", 0),
        "summary": block.get("summary", "")
    }
    response = requests.post(url, headers=headers, data=json.dumps(serialize_for_json(payload)))
    if not response.status_code in (200, 201):
        raise Exception("Failed to save tokenized history:", response.json().get("detail", response.text))

def delete_latest_history_entry(token, game_id):
    # Fetch all history entries for the game
    url = f"{API_SERVER_URL}/history/?saved_game_id={game_id}"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise Exception("Failed to fetch history entries for deletion.")
        return False
    history_entries = response.json()
    if not history_entries:
        raise Exception("No history entries to delete.")
        return False
    latest_entry = history_entries[-1]
    entry_id = latest_entry.get("id")
    if not entry_id:
        raise Exception("Latest entry does not have an ID.")
        return False
    # Delete the latest entry
    del_url = f"{API_SERVER_URL}/history/{entry_id}"
    del_resp = requests.delete(del_url, headers=headers)
    if del_resp.status_code in (200, 204):
        return True
    else:
        raise Exception("Failed to delete latest history entry.")
        return False

def fetch_worlds_and_ratings():
    worlds_resp = requests.get(f"{API_SERVER_URL}/worlds/")
    ratings_resp = requests.get(f"{API_SERVER_URL}/game_ratings/")
    worlds = {w['id']: w for w in worlds_resp.json()} if worlds_resp.status_code == 200 else {}
    ratings = {r['id']: r for r in ratings_resp.json()} if ratings_resp.status_code == 200 else {}
    return worlds, ratings
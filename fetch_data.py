import requests
import pandas as pd
from sqlalchemy import create_engine
import time

DB_URL = "postgresql://postgres:reesepot@localhost:5432/steamdb"
engine = create_engine(DB_URL)

def fetch_all_app_ids():
    """Get list of all app IDs first"""
    url = "https://steamspy.com/api.php?request=all&page=0"
    print("Fetching game list...")
    response = requests.get(url, timeout=30)
    data = response.json()
    print(f"Got {len(data)} game IDs")
    return list(data.keys())

def fetch_game_details(app_id):
    """Fetch full details for one game"""
    url = f"https://steamspy.com/api.php?request=appdetails&appid={app_id}"
    response = requests.get(url, timeout=30)
    if response.status_code == 200:
        return response.json()
    return None

def clean_game(game, app_id):
    tags = game.get("tags", {})
    tags_str = ", ".join(tags.keys()) if isinstance(tags, dict) else ""
    return {
        "app_id": int(app_id),
        "name": game.get("name", ""),
        "developer": game.get("developer", ""),
        "publisher": game.get("publisher", ""),
        "genre": game.get("genre", ""),
        "tags": tags_str,
        "price": round(int(game.get("price", 0)) / 100, 2),
        "discount": int(game.get("discount", 0)),
        "score_rank": game.get("score_rank") or 0,
        "positive": game.get("positive", 0),
        "negative": game.get("negative", 0),
        "owners": game.get("owners", ""),
        "ccu": game.get("ccu", 0),
        "average_forever": game.get("average_forever", 0),
        "languages": game.get("languages", ""),
    }

if __name__ == "__main__":
    app_ids = fetch_all_app_ids()
    
    rows = []
    failed = []
    
    for i, app_id in enumerate(app_ids):
        try:
            game = fetch_game_details(app_id)
            if game and game.get("name"):
                rows.append(clean_game(game, app_id))
            
            # Print progress every 50 games
            if (i + 1) % 50 == 0:
                print(f"Progress: {i + 1}/{len(app_ids)} games fetched...")
            
            # Wait 1 second between requests so SteamSpy doesn't block us
            time.sleep(1)

        except Exception as e:
            print(f"Failed on app_id {app_id}: {e}")
            failed.append(app_id)
            continue
    
    print(f"\nDone fetching! Got {len(rows)} games, {len(failed)} failed.")
    print("Saving to database...")
    
    df = pd.DataFrame(rows)
    df.to_sql("games", engine, if_exists="replace", index=False)
    
    print("Saved! Check TablePlus.")
import requests
import pandas as pd
from sqlalchemy import create_engine
import time
import os

# In GitHub Actions, this comes from a GitHub Secret, not hardcoded
SUPABASE_URL = os.environ.get("SUPABASE_URL", "postgresql://postgres.zkuwloytmvyqxdlfobax:yourpassword@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres")
supabase_engine = create_engine(SUPABASE_URL)

PAGES_TO_FETCH = [0, 1, 2, 3, 4]  # all 5 pages, since this script no longer depends on prior local data

def fetch_page_app_ids(page):
    url = f"https://steamspy.com/api.php?request=all&page={page}"
    print(f"Fetching page {page} game list...")
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    data = response.json()
    print(f"  Got {len(data)} game IDs from page {page}")
    return list(data.keys())

def fetch_game_details(app_id):
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

def price_tier(price):
    if price == 0:
        return "Free"
    elif price < 5:
        return "Under $5"
    elif price < 15:
        return "$5–$15"
    elif price < 30:
        return "$15–$30"
    else:
        return "$30+"

if __name__ == "__main__":
    # --- Step 1: Fetch ---
    all_app_ids = []
    for page in PAGES_TO_FETCH:
        ids = fetch_page_app_ids(page)
        all_app_ids.extend(ids)
        time.sleep(1)

    print(f"\nTotal app IDs to fetch: {len(all_app_ids)}")

    rows = []
    failed = []

    for i, app_id in enumerate(all_app_ids):
        try:
            game = fetch_game_details(app_id)
            if game and game.get("name"):
                rows.append(clean_game(game, app_id))
            if (i + 1) % 100 == 0:
                print(f"Progress: {i + 1}/{len(all_app_ids)} games fetched...")
            time.sleep(1)
        except Exception as e:
            print(f"Failed on app_id {app_id}: {e}")
            failed.append(app_id)
            continue

    print(f"\nFetch done. Got {len(rows)} games, {len(failed)} failed.")

    # Safety check: if almost everything failed, stop here rather than
    # overwriting good Supabase data with a near-empty/broken dataset
    if len(rows) < len(all_app_ids) * 0.5:
        raise RuntimeError(
            f"Too many failures ({len(failed)}/{len(all_app_ids)}). "
            f"Aborting before touching Supabase to avoid overwriting good data with bad data."
        )

    df = pd.DataFrame(rows)
    df = df.drop_duplicates(subset="app_id", keep="last")

    # --- Step 2: Clean (merged in-memory, no local Postgres step) ---
    print("\nCleaning data...")
    df["total_reviews"] = df["positive"] + df["negative"]
    df["review_score"] = df.apply(
        lambda row: round(row["positive"] / row["total_reviews"] * 100, 1)
        if row["total_reviews"] > 0 else None,
        axis=1
    )
    df["price_tier"] = df["price"].apply(price_tier)
    df["primary_genre"] = df["genre"].str.split(",").str[0].str.strip()

    genre_rows = []
    for _, row in df.iterrows():
        if row["genre"]:
            for genre in [g.strip() for g in row["genre"].split(",")]:
                genre_rows.append({
                    "app_id": row["app_id"], "name": row["name"], "genre": genre,
                    "price": row["price"], "price_tier": row["price_tier"],
                    "review_score": row["review_score"], "total_reviews": row["total_reviews"],
                    "owners": row["owners"], "ccu": row["ccu"],
                })
    df_genres = pd.DataFrame(genre_rows)

    tag_rows = []
    for _, row in df.iterrows():
        if row["tags"]:
            for tag in [t.strip() for t in row["tags"].split(",")]:
                tag_rows.append({
                    "app_id": row["app_id"], "name": row["name"], "tag": tag,
                    "price": row["price"], "review_score": row["review_score"],
                    "total_reviews": row["total_reviews"], "owners": row["owners"],
                })
    df_tags = pd.DataFrame(tag_rows)

    # --- Step 3: Write to Supabase only after everything above succeeded ---
    # --- Step 3: Write to Supabase atomically ---
    # Write to temp table names first. Only rename into the real table names
    # if all three writes succeed, so the live site never sees a half-updated,
    # inconsistent set of tables if something crashes partway through.
    print("\nWriting to Supabase (staging)...")

    df.to_sql("games_clean_staging", supabase_engine, if_exists="replace", index=False)
    print(f"  games_clean_staging: {len(df)} rows")

    df_genres.to_sql("games_genres_exploded_staging", supabase_engine, if_exists="replace", index=False)
    print(f"  games_genres_exploded_staging: {len(df_genres)} rows")

    df_tags.to_sql("games_tags_exploded_staging", supabase_engine, if_exists="replace", index=False)
    print(f"  games_tags_exploded_staging: {len(df_tags)} rows")

    print("\nAll staging writes succeeded. Promoting to live tables...")

    with supabase_engine.begin() as conn:
        # Drop old live tables and rename staging into their place, inside one transaction
        conn.exec_driver_sql("DROP TABLE IF EXISTS games_clean_old")
        conn.exec_driver_sql("DROP TABLE IF EXISTS games_genres_exploded_old")
        conn.exec_driver_sql("DROP TABLE IF EXISTS games_tags_exploded_old")

        conn.exec_driver_sql("ALTER TABLE IF EXISTS games_clean RENAME TO games_clean_old")
        conn.exec_driver_sql("ALTER TABLE IF EXISTS games_genres_exploded RENAME TO games_genres_exploded_old")
        conn.exec_driver_sql("ALTER TABLE IF EXISTS games_tags_exploded RENAME TO games_tags_exploded_old")

        conn.exec_driver_sql("ALTER TABLE games_clean_staging RENAME TO games_clean")
        conn.exec_driver_sql("ALTER TABLE games_genres_exploded_staging RENAME TO games_genres_exploded")
        conn.exec_driver_sql("ALTER TABLE games_tags_exploded_staging RENAME TO games_tags_exploded")

        conn.exec_driver_sql("DROP TABLE IF EXISTS games_clean_old")
        conn.exec_driver_sql("DROP TABLE IF EXISTS games_genres_exploded_old")
        conn.exec_driver_sql("DROP TABLE IF EXISTS games_tags_exploded_old")

    print("Done. Live tables updated.")
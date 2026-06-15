import pandas as pd
from sqlalchemy import create_engine

DB_URL = "postgresql://postgres:reesepot@localhost:5432/steamdb"
engine = create_engine(DB_URL)

print("Loading data...")
df = pd.read_sql("SELECT * FROM games", engine)
print(f"Loaded {len(df)} games")

# --- 1. Add total reviews and review score ---
df["total_reviews"] = df["positive"] + df["negative"]

df["review_score"] = df.apply(
    lambda row: round(row["positive"] / row["total_reviews"] * 100, 1)
    if row["total_reviews"] > 0 else None,
    axis=1
)

# --- 2. Add price tier ---
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

df["price_tier"] = df["price"].apply(price_tier)

# --- 3. Add primary genre (first listed) ---
df["primary_genre"] = df["genre"].str.split(",").str[0].str.strip()

# --- 4. Save main cleaned table ---
print("Saving games_clean table...")
df.to_sql("games_clean", engine, if_exists="replace", index=False)
print(f"Saved {len(df)} rows to games_clean")

# --- 5. Create exploded genre table ---
# Each row = one genre tag for one game
# So a game with 3 genres becomes 3 rows
print("Creating exploded genre table...")
genre_rows = []
for _, row in df.iterrows():
    if row["genre"]:
        genres = [g.strip() for g in row["genre"].split(",")]
        for genre in genres:
            genre_rows.append({
                "app_id": row["app_id"],
                "name": row["name"],
                "genre": genre,
                "price": row["price"],
                "price_tier": row["price_tier"],
                "review_score": row["review_score"],
                "total_reviews": row["total_reviews"],
                "owners": row["owners"],
                "ccu": row["ccu"],
            })

df_genres = pd.DataFrame(genre_rows)
df_genres.to_sql("games_genres_exploded", engine, if_exists="replace", index=False)
print(f"Saved {len(df_genres)} rows to games_genres_exploded")

# --- 6. Create exploded tags table ---
print("Creating exploded tags table...")
tag_rows = []
for _, row in df.iterrows():
    if row["tags"]:
        tags = [t.strip() for t in row["tags"].split(",")]
        for tag in tags:
            tag_rows.append({
                "app_id": row["app_id"],
                "name": row["name"],
                "tag": tag,
                "price": row["price"],
                "review_score": row["review_score"],
                "total_reviews": row["total_reviews"],
                "owners": row["owners"],
            })

df_tags = pd.DataFrame(tag_rows)
df_tags.to_sql("games_tags_exploded", engine, if_exists="replace", index=False)
print(f"Saved {len(df_tags)} rows to games_tags_exploded")

# --- 7. Print summary ---
print("\n--- Summary ---")
print(f"Total games: {len(df)}")
print(f"\nPrice tiers:\n{df['price_tier'].value_counts()}")
print(f"\nTop 10 primary genres:\n{df['primary_genre'].value_counts().head(10)}")
print(f"\nTop 10 individual genres (exploded):\n{df_genres['genre'].value_counts().head(10)}")
print(f"\nTop 15 tags:\n{df_tags['tag'].value_counts().head(15)}")
print(f"\nGames with no reviews: {len(df[df['total_reviews'] == 0])}")
print(f"Games with 1-50 reviews: {len(df[(df['total_reviews'] > 0) & (df['total_reviews'] <= 50)])}")
print(f"Games with 50+ reviews: {len(df[df['total_reviews'] > 50])}")
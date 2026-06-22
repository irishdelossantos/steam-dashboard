from dotenv import load_dotenv
import pandas as pd
from sqlalchemy import create_engine
import os

load_dotenv()

LOCAL_URL = "postgresql://postgres:reesepot@localhost:5432/steamdb"
SUPABASE_URL = os.environ.get("SUPABASE_URL")

if not SUPABASE_URL:
    raise RuntimeError(
        "SUPABASE_URL not found. Make sure it's set in your .env file, "
        "e.g. SUPABASE_URL=postgresql://postgres.xxxx:yourpassword@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres"
    )

local_engine = create_engine(LOCAL_URL)
supabase_engine = create_engine(SUPABASE_URL)

tables = ["games_clean", "games_genres_exploded", "games_tags_exploded"]

for table in tables:
    print(f"Migrating {table}...")
    df = pd.read_sql(f"SELECT * FROM {table}", local_engine)
    print(f"  Read {len(df)} rows from local")
    df.to_sql(table, supabase_engine, if_exists="replace", index=False)
    print(f"  Saved to Supabase ✓")

print("\nAll done! Check Supabase table editor to verify.")
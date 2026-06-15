import pandas as pd
from sqlalchemy import create_engine
import os

DB_URL = "postgresql://postgres:reesepot@localhost:5432/steamdb"
engine = create_engine(DB_URL)

# Load data
df = pd.read_sql("SELECT * FROM games", engine)

output = []
output.append(f"Total rows: {len(df)}\n")

output.append("--- Column info ---")
output.append(str(df.dtypes))

output.append("\n--- Missing values per column ---")
output.append(str(df.isnull().sum()))

output.append("\n--- Price range ---")
output.append(str(df["price"].describe()))

output.append("\n--- Genre breakdown ---")
output.append(str(df["genre"].value_counts().head(20)))

output.append("\n--- Sample of tags (first 10 rows) ---")
output.append(str(df["tags"].head(10)))

output.append("\n--- Owners breakdown ---")
output.append(str(df["owners"].value_counts().head(10)))

output.append("\n--- Sample rows ---")
output.append(str(df[["name", "genre", "price", "positive", "negative", "tags"]].head(20).to_string()))

# Save to file
output_path = os.path.join(os.path.dirname(__file__), "data_info.txt")
with open(output_path, "w") as f:
    f.write("\n".join(output))

print("Done! Check data_info.txt in your project folder.")
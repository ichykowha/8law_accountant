import time
from pinecone import Pinecone, ServerlessSpec

# --- CONFIGURATION ---
# Replace the text inside the quotes with your actual API key
api_key = "pcsk_c3qC4_4VCCbCQzm7teBF7goTsnVYEFeriSWxNJQ7JUALzwivsRtRnCE4ZsutWCgELuhFC"
index_name = "test-index-001"

# --- INITIALIZE ---
print("Connecting to Pinecone...")
pc = Pinecone(api_key=api_key)

# --- CREATE INDEX ---
# We check if the index exists first. If not, we create it.
existing_indexes = [index_info["name"] for index_info in pc.list_indexes()]

if index_name not in existing_indexes:
    print(f"Creating index '{index_name}'...")
    pc.create_index(
        name=index_name,
        dimension=3, # Example dimension size
        metric="cosine",
        spec=ServerlessSpec(
            cloud="aws",
            region="us-east-1"
        )
    )
    # Wait a moment for the index to be ready
    while not pc.describe_index(index_name).status['ready']:
        time.sleep(1)
else:
    print(f"Index '{index_name}' already exists.")

# --- CONNECT TO INDEX ---
index = pc.Index(index_name)

# --- ADD DATA (Upsert) ---
print("Adding dummy data...")
# Format: (id, vector_values)
index.upsert(
    vectors=[
        ("vec1", [0.1, 0.2, 0.3]),
        ("vec2", [0.4, 0.5, 0.6])
    ]
)

# --- SEARCH DATA (Query) ---
print("Querying data...")
query_results = index.query(
    vector=[0.1, 0.2, 0.3],
    top_k=1,
    include_values=True
)

print("Results found:")
print(query_results)

print("Success! Pinecone is working.")
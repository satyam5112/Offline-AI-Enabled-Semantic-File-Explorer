from backend.search.search import search_files

def run_cli():
    print("🔎 Advanced Semantic Search (type 'exit' to quit)\n")

    while True:
        query = input("Enter search query: ").strip()

        if not query:
            print("⚠️ Please enter a valid search query\n")
            continue

        if query.lower() == "exit":
            break

        file_type = input("Filter by extension (optional): ").strip() or None
        folder = input("Filter by folder (optional): ").strip() or None

        results = search_files(query, file_type=file_type, folder=folder)

        print("\n📄 Results:\n")

        for i, r in enumerate(results, 1):
            print(f"{i}. {r['file_name']} ({r['folder']})")
            print(f"   Score: {round(r['score'], 3)}")
            print(f"   → {r['chunk'][:200]}...\n")


if __name__ == "__main__":
    run_cli()
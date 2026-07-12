from app.servicos.migrations import run_migrations

if __name__ == "__main__":
    applied = run_migrations()
    if applied:
        for version in applied:
            print(f"Aplicada: {version}")
    else:
        print("Nenhuma migration pendente.")

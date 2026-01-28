import app.auth_supabase as auth

def main():
    auth.require_login()

if __name__ == "__main__":
    main()

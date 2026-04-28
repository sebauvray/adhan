#!/usr/bin/env python3
"""Admin account management CLI for Adhan Home.

Run inside the web container:

    docker exec -it adhan-web python3 /app/admin_reset.py

Without arguments, opens an interactive menu. Non-interactive forms:

    python3 admin_reset.py list
    python3 admin_reset.py create <username>
    python3 admin_reset.py reset  <username>
    python3 admin_reset.py delete <username>
"""
import sys
import getpass

sys.path.insert(0, '/app')

from db.schema import init_db
from db.config import (
    create_auth, list_auth, update_auth_password, delete_auth,
)


def _prompt_password():
    while True:
        p1 = getpass.getpass("Mot de passe (8 caractères min) : ")
        if len(p1) < 8:
            print("Trop court, recommence.")
            continue
        p2 = getpass.getpass("Confirmer : ")
        if p1 != p2:
            print("Ne correspondent pas, recommence.")
            continue
        return p1


def cmd_list():
    rows = list_auth()
    if not rows:
        print("Aucun compte admin.")
        return
    print(f"{'ID':<4} {'Identifiant':<24} {'Créé le'}")
    print("-" * 60)
    for r in rows:
        print(f"{r['id']:<4} {r['username']:<24} {r['created_at']}")


def cmd_create(username=None):
    if not username:
        username = input("Identifiant : ").strip()
    if len(username) < 3:
        print("Identifiant trop court (3 caractères minimum).")
        sys.exit(1)
    pwd = _prompt_password()
    try:
        create_auth(username, pwd)
        print(f"Compte '{username}' créé.")
    except Exception as e:
        print(f"Erreur : {e}")
        sys.exit(1)


def cmd_reset(username=None):
    if not username:
        username = input("Identifiant à réinitialiser : ").strip()
    pwd = _prompt_password()
    if update_auth_password(username, pwd):
        print(f"Mot de passe de '{username}' réinitialisé. Sessions actives invalidées.")
    else:
        print(f"Aucun compte '{username}'.")
        sys.exit(1)


def cmd_delete(username=None):
    if not username:
        username = input("Identifiant à supprimer : ").strip()
    confirm = input(f"Supprimer le compte '{username}' ? [oui/non] ").strip().lower()
    if confirm not in ('oui', 'o', 'yes', 'y'):
        print("Annulé.")
        return
    if delete_auth(username):
        print(f"Compte '{username}' supprimé.")
    else:
        print(f"Aucun compte '{username}'.")


def menu():
    while True:
        print("\n=== Adhan Home — Gestion compte admin ===")
        print("1) Lister les comptes")
        print("2) Créer un compte")
        print("3) Réinitialiser un mot de passe")
        print("4) Supprimer un compte")
        print("0) Quitter")
        try:
            choice = input("Choix : ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == '1':
            cmd_list()
        elif choice == '2':
            cmd_create()
        elif choice == '3':
            cmd_reset()
        elif choice == '4':
            cmd_delete()
        elif choice == '0':
            return
        else:
            print("Choix invalide.")


def main():
    init_db()
    if len(sys.argv) == 1:
        menu()
        return
    cmd = sys.argv[1]
    arg = sys.argv[2] if len(sys.argv) > 2 else None
    if cmd == 'list':
        cmd_list()
    elif cmd == 'create':
        cmd_create(arg)
    elif cmd == 'reset':
        cmd_reset(arg)
    elif cmd == 'delete':
        cmd_delete(arg)
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == '__main__':
    main()

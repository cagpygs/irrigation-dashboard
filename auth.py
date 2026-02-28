from db import get_connection

def check_login(username, password):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, username, role
        FROM users
        WHERE username=%s AND password=%s
    """, (username, password))

    row = cur.fetchone()
    conn.close()

    if row:
        return {
            "id": row[0],
            "username": row[1],
            "role": row[2]
        }
    return None
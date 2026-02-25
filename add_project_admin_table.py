#!/usr/bin/env python3
"""Create project_admin table."""

import sqlite3

def main():
    db_path = 'instance_dev/datatracker_dev.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS project_admin (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id VARCHAR(50) NOT NULL,
                user_id INTEGER NOT NULL,
                added_at DATETIME,
                FOREIGN KEY (project_id) REFERENCES project(id),
                FOREIGN KEY (user_id) REFERENCES user(id),
                UNIQUE (project_id, user_id)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_project_admin_project_id ON project_admin(project_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_project_admin_user_id ON project_admin(user_id)")
        conn.commit()
        print("project_admin table created.")
    finally:
        conn.close()

if __name__ == '__main__':
    main()

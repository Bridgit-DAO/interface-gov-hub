#!/usr/bin/env python3
"""Update operational names for Meta-Layer roles as specified."""

import sqlite3

UPDATES = [
    ("keeper-of-the-commons", "RFC Governance Substrate Lead"),
    ("alignment-steward", "AI Ethics & Policy Lead"),
    ("flourishing-steward", "Human Flourishing Lead"),
    ("policy-steward", "Policy Coordinator"),
    ("legal-steward", "Legal"),
    ("sensemaking-steward", "Collective Intelligence Lead"),
    ("keeper-of-lineage", "Badge System Manager"),
    ("voice-of-the-guilds", "Podcast Producer"),
]

PROJECT_ID = "proj_dfupe6bwkkul"  # the-meta-layer

def main():
    db_path = "instance_dev/datatracker_dev.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    for role_slug, title_operational in UPDATES:
        cursor.execute(
            "UPDATE role SET title_operational = ? WHERE project_id = ? AND role_slug = ?",
            (title_operational, PROJECT_ID, role_slug),
        )
        if cursor.rowcount:
            print(f"  ✓ {role_slug} → {title_operational}")
        else:
            print(f"  - {role_slug} (no row updated)")

    conn.commit()
    conn.close()
    print("Done.")

if __name__ == "__main__":
    main()

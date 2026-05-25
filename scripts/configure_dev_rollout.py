#!/usr/bin/env python3
"""Set dev-friendly product rollout flags (run from gov-hub-dev with app context)."""
from app import create_app
from services.product_rollout import set_rollout_config, get_rollout_config

# Features to activate on dev for layer/guild/waitlist tuning
DEV_ROLLOUT = {
    'layers': True,
    'docs': True,
    'guilds': True,
    'waitlists': True,
    'roles': True,
    'badges': True,
    'workgroups': True,
    'admin': True,
    # Off until you want them on dev
    'votes': False,
    'artifacts': False,
    'quests': False,
    'opportunities': False,
    'bridges': False,
    'civic_mason': False,
    'soft_launch': False,
    'immortalize': False,
}


def main():
    app = create_app()
    with app.app_context():
        set_rollout_config(DEV_ROLLOUT)
        cfg = get_rollout_config()
        print('Product rollout updated:')
        for k in sorted(cfg.keys()):
            print(f'  {k}: {cfg[k]}')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Import Meta-Layer clusters and roles
"""
import json
import requests
import sys

# Configuration
BASE_URL = "http://localhost:8001"
PROJECT_ID = "proj_dfupe6bwkkul"

# You need to provide a valid session cookie or auth token
# Get this from your browser after logging in as admin
AUTH_COOKIE = input("Enter your session cookie value: ").strip()

session = requests.Session()
session.cookies.set('session', AUTH_COOKIE)

# Clusters data
clusters_data = {
    "clusters": [
        {
            "name": "Core Stewardship & Coherence",
            "description": "Roles that steward coherence, ethics, policy, law, sensemaking, and overall direction without centralizing control.",
            "order": 10
        },
        {
            "name": "Infrastructure & Standards",
            "description": "Roles that build, maintain, and steward technical infrastructure, interfaces, agents, and standards alignment.",
            "order": 20
        },
        {
            "name": "Narrative, Presence & Convening",
            "description": "Roles that shape narrative, steward public presence, host events, and maintain communication channels.",
            "order": 30
        },
        {
            "name": "Working Groups & Research",
            "description": "Roles that coordinate and contribute to focused working groups, research efforts, and draft production.",
            "order": 40
        },
        {
            "name": "Growth, Partnerships & Resources",
            "description": "Roles that steward partnerships, funding, grants, and external resource flows.",
            "order": 50
        }
    ]
}

# Roles data
roles_data = {
    "roles": [
        {
            "titleGuild": "Bridger",
            "titleOperational": "Director",
            "description": "Stewards strategic, ethical, and narrative coherence across the Meta-Layer.",
            "clusterName": "Core Stewardship & Coherence",
            "claimRequiresApproval": False,
            "badgeEnabled": True,
            "badgeRequiresApproval": True,
            "publicVisible": True
        },
        {
            "titleGuild": "Keeper of the Commons",
            "titleOperational": None,
            "description": "Stewards shared governance artifacts, RFC processes, and institutional memory.",
            "clusterName": "Core Stewardship & Coherence",
            "claimRequiresApproval": False,
            "badgeEnabled": True,
            "badgeRequiresApproval": True,
            "publicVisible": True
        },
        {
            "titleGuild": "Alignment Steward",
            "titleOperational": None,
            "description": "Ensures human values, AI coexistence, and ethical alignment across workstreams.",
            "clusterName": "Core Stewardship & Coherence",
            "claimRequiresApproval": False,
            "badgeEnabled": True,
            "badgeRequiresApproval": True,
            "publicVisible": True
        },
        {
            "titleGuild": "Flourishing Steward",
            "titleOperational": None,
            "description": "Stewards human wellbeing, sustainability, and regenerative practices.",
            "clusterName": "Core Stewardship & Coherence",
            "claimRequiresApproval": False,
            "badgeEnabled": True,
            "badgeRequiresApproval": True,
            "publicVisible": True
        },
        {
            "titleGuild": "Policy Steward",
            "titleOperational": None,
            "description": "Interfaces with public policy, governance frameworks, and regulatory considerations.",
            "clusterName": "Core Stewardship & Coherence",
            "claimRequiresApproval": False,
            "badgeEnabled": True,
            "badgeRequiresApproval": True,
            "publicVisible": True
        },
        {
            "titleGuild": "Legal Steward",
            "titleOperational": None,
            "description": "Provides legal insight and risk awareness without exerting control.",
            "clusterName": "Core Stewardship & Coherence",
            "claimRequiresApproval": False,
            "badgeEnabled": True,
            "badgeRequiresApproval": True,
            "publicVisible": True
        },
        {
            "titleGuild": "Sensemaking Steward",
            "titleOperational": None,
            "description": "Synthesizes patterns across signals, communities, and workstreams.",
            "clusterName": "Core Stewardship & Coherence",
            "claimRequiresApproval": False,
            "badgeEnabled": True,
            "badgeRequiresApproval": True,
            "publicVisible": True
        },
        {
            "titleGuild": "Infrastructure Builder",
            "titleOperational": "Developer",
            "description": "Builds and maintains core technical infrastructure.",
            "clusterName": "Infrastructure & Standards",
            "claimRequiresApproval": False,
            "badgeEnabled": True,
            "badgeRequiresApproval": True,
            "publicVisible": True
        },
        {
            "titleGuild": "Agent Architect",
            "titleOperational": "Agent Developer",
            "description": "Designs and implements agent-based systems aligned with Meta-Layer principles.",
            "clusterName": "Infrastructure & Standards",
            "claimRequiresApproval": False,
            "badgeEnabled": True,
            "badgeRequiresApproval": True,
            "publicVisible": True
        },
        {
            "titleGuild": "Interface Shaper",
            "titleOperational": "Designer",
            "description": "Designs interfaces and overlays that shape human–AI interaction.",
            "clusterName": "Infrastructure & Standards",
            "claimRequiresApproval": False,
            "badgeEnabled": True,
            "badgeRequiresApproval": True,
            "publicVisible": True
        },
        {
            "titleGuild": "Web Custodian",
            "titleOperational": "Website Maintenance",
            "description": "Maintains websites, domains, and web presence.",
            "clusterName": "Infrastructure & Standards",
            "claimRequiresApproval": False,
            "badgeEnabled": True,
            "badgeRequiresApproval": True,
            "publicVisible": True
        },
        {
            "titleGuild": "Keeper of Lineage",
            "titleOperational": None,
            "description": "Maintains provenance, attribution, and historical continuity.",
            "clusterName": "Infrastructure & Standards",
            "claimRequiresApproval": False,
            "badgeEnabled": True,
            "badgeRequiresApproval": True,
            "publicVisible": True
        },
        {
            "titleGuild": "Narrative Steward",
            "titleOperational": "Content Lead",
            "description": "Shapes and curates the Meta-Layer narrative across channels.",
            "clusterName": "Narrative, Presence & Convening",
            "claimRequiresApproval": False,
            "badgeEnabled": True,
            "badgeRequiresApproval": True,
            "publicVisible": True
        },
        {
            "titleGuild": "Voice of the Guilds",
            "titleOperational": None,
            "description": "Amplifies guild activity and cross-guild communication.",
            "clusterName": "Narrative, Presence & Convening",
            "claimRequiresApproval": False,
            "badgeEnabled": True,
            "badgeRequiresApproval": True,
            "publicVisible": True
        },
        {
            "titleGuild": "Presence Steward – X",
            "titleOperational": "X Manager",
            "description": "Stewards presence and discourse on X.",
            "clusterName": "Narrative, Presence & Convening",
            "claimRequiresApproval": False,
            "badgeEnabled": True,
            "badgeRequiresApproval": True,
            "publicVisible": True
        },
        {
            "titleGuild": "Presence Steward – LinkedIn",
            "titleOperational": "LinkedIn Manager",
            "description": "Stewards presence and discourse on LinkedIn.",
            "clusterName": "Narrative, Presence & Convening",
            "claimRequiresApproval": False,
            "badgeEnabled": True,
            "badgeRequiresApproval": True,
            "publicVisible": True
        },
        {
            "titleGuild": "Presence Steward – WhatsApp",
            "titleOperational": "WhatsApp Manager",
            "description": "Stewards coordination and communication via WhatsApp.",
            "clusterName": "Narrative, Presence & Convening",
            "claimRequiresApproval": False,
            "badgeEnabled": True,
            "badgeRequiresApproval": True,
            "publicVisible": True
        },
        {
            "titleGuild": "Session Steward",
            "titleOperational": "Events Manager",
            "description": "Hosts and facilitates sessions, workshops, and calls.",
            "clusterName": "Narrative, Presence & Convening",
            "claimRequiresApproval": False,
            "badgeEnabled": True,
            "badgeRequiresApproval": True,
            "publicVisible": True
        },
        {
            "titleGuild": "Workstream Steward",
            "titleOperational": "Working Group Coordinator",
            "description": "Coordinates focused working groups and deliverables.",
            "clusterName": "Working Groups & Research",
            "claimRequiresApproval": False,
            "badgeEnabled": True,
            "badgeRequiresApproval": True,
            "publicVisible": True
        },
        {
            "titleGuild": "Working Group Contributor",
            "titleOperational": "Working Group Member",
            "description": "Contributes to working group research and outputs.",
            "clusterName": "Working Groups & Research",
            "claimRequiresApproval": False,
            "badgeEnabled": True,
            "badgeRequiresApproval": False,
            "publicVisible": True
        },
        {
            "titleGuild": "Bridge Builder",
            "titleOperational": "Business Development",
            "description": "Cultivates partnerships and external relationships.",
            "clusterName": "Growth, Partnerships & Resources",
            "claimRequiresApproval": False,
            "badgeEnabled": True,
            "badgeRequiresApproval": True,
            "publicVisible": True
        },
        {
            "titleGuild": "Resource Steward",
            "titleOperational": "Grants",
            "description": "Stewards funding, grants, and resource flows.",
            "clusterName": "Growth, Partnerships & Resources",
            "claimRequiresApproval": False,
            "badgeEnabled": True,
            "badgeRequiresApproval": True,
            "publicVisible": True
        }
    ]
}

def import_clusters():
    """Import clusters and return cluster name to ID mapping"""
    print("\n=== Importing Clusters ===")
    cluster_map = {}
    
    for cluster in clusters_data['clusters']:
        print(f"\nCreating cluster: {cluster['name']}")
        response = session.post(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/clusters/",
            json=cluster,
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code in [200, 201]:
            result = response.json()
            cluster_id = result['cluster']['id']
            cluster_map[cluster['name']] = cluster_id
            print(f"  ✓ Created: {cluster_id}")
        else:
            print(f"  ✗ Error: {response.status_code} - {response.text}")
    
    return cluster_map

def import_roles(cluster_map):
    """Import roles using cluster mapping"""
    print("\n=== Importing Roles ===")
    
    # Transform roles data to match API format
    api_roles = []
    for role in roles_data['roles']:
        api_role = {
            'title_guild': role['titleGuild'],
            'title_operational': role['titleOperational'],
            'description': role['description'],
            'cluster_id': cluster_map.get(role['clusterName']),
            'claim_requires_approval': role['claimRequiresApproval'],
            'badge_enabled': role['badgeEnabled'],
            'badge_requires_approval': role['badgeRequiresApproval'],
            'public_visible': role['publicVisible']
        }
        api_roles.append(api_role)
    
    print(f"\nImporting {len(api_roles)} roles...")
    response = session.post(
        f"{BASE_URL}/api/projects/{PROJECT_ID}/roles/import/",
        json={'roles': api_roles},
        headers={'Content-Type': 'application/json'}
    )
    
    if response.status_code in [200, 201]:
        result = response.json()
        print(f"\n✓ Successfully imported {result['imported_count']} roles")
        if result.get('errors'):
            print(f"\n⚠ Errors encountered:")
            for error in result['errors']:
                print(f"  - {error}")
    else:
        print(f"\n✗ Error: {response.status_code}")
        print(response.text)

def main():
    print("=" * 60)
    print("Meta-Layer Data Import")
    print("=" * 60)
    
    # Import clusters first
    cluster_map = import_clusters()
    
    if not cluster_map:
        print("\n✗ No clusters were created. Aborting role import.")
        sys.exit(1)
    
    print(f"\n✓ Created {len(cluster_map)} clusters")
    
    # Import roles
    import_roles(cluster_map)
    
    print("\n" + "=" * 60)
    print("Import Complete!")
    print("=" * 60)

if __name__ == '__main__':
    main()

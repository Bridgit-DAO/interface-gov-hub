#!/usr/bin/env python3
"""
Import Meta-Layer clusters and roles directly to database
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from ietf_data_viewer_simple import db, Project, Cluster, Role, app
from datetime import datetime
import random
import string

PROJECT_SLUG = "the-meta-layer"

def generate_id(prefix, length=12):
    """Generate a random ID with prefix"""
    chars = string.ascii_lowercase + string.digits
    suffix = ''.join(random.choice(chars) for _ in range(length))
    return f"{prefix}_{suffix}"

def create_slug(text):
    """Create URL-friendly slug"""
    import re
    slug = text.lower()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[-\s]+', '-', slug)
    return slug.strip('-')

# Clusters data
clusters_data = [
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

# Roles data
roles_data = [
    {"titleGuild": "Bridger", "titleOperational": "Director", "description": "Stewards strategic, ethical, and narrative coherence across the Meta-Layer.", "clusterName": "Core Stewardship & Coherence", "claimRequiresApproval": False, "badgeEnabled": True, "badgeRequiresApproval": True, "publicVisible": True},
    {"titleGuild": "Keeper of the Commons", "titleOperational": None, "description": "Stewards shared governance artifacts, RFC processes, and institutional memory.", "clusterName": "Core Stewardship & Coherence", "claimRequiresApproval": False, "badgeEnabled": True, "badgeRequiresApproval": True, "publicVisible": True},
    {"titleGuild": "Alignment Steward", "titleOperational": None, "description": "Ensures human values, AI coexistence, and ethical alignment across workstreams.", "clusterName": "Core Stewardship & Coherence", "claimRequiresApproval": False, "badgeEnabled": True, "badgeRequiresApproval": True, "publicVisible": True},
    {"titleGuild": "Flourishing Steward", "titleOperational": None, "description": "Stewards human wellbeing, sustainability, and regenerative practices.", "clusterName": "Core Stewardship & Coherence", "claimRequiresApproval": False, "badgeEnabled": True, "badgeRequiresApproval": True, "publicVisible": True},
    {"titleGuild": "Policy Steward", "titleOperational": None, "description": "Interfaces with public policy, governance frameworks, and regulatory considerations.", "clusterName": "Core Stewardship & Coherence", "claimRequiresApproval": False, "badgeEnabled": True, "badgeRequiresApproval": True, "publicVisible": True},
    {"titleGuild": "Legal Steward", "titleOperational": None, "description": "Provides legal insight and risk awareness without exerting control.", "clusterName": "Core Stewardship & Coherence", "claimRequiresApproval": False, "badgeEnabled": True, "badgeRequiresApproval": True, "publicVisible": True},
    {"titleGuild": "Sensemaking Steward", "titleOperational": None, "description": "Synthesizes patterns across signals, communities, and workstreams.", "clusterName": "Core Stewardship & Coherence", "claimRequiresApproval": False, "badgeEnabled": True, "badgeRequiresApproval": True, "publicVisible": True},
    {"titleGuild": "Infrastructure Builder", "titleOperational": "Developer", "description": "Builds and maintains core technical infrastructure.", "clusterName": "Infrastructure & Standards", "claimRequiresApproval": False, "badgeEnabled": True, "badgeRequiresApproval": True, "publicVisible": True},
    {"titleGuild": "Agent Architect", "titleOperational": "Agent Developer", "description": "Designs and implements agent-based systems aligned with Meta-Layer principles.", "clusterName": "Infrastructure & Standards", "claimRequiresApproval": False, "badgeEnabled": True, "badgeRequiresApproval": True, "publicVisible": True},
    {"titleGuild": "Interface Shaper", "titleOperational": "Designer", "description": "Designs interfaces and overlays that shape human–AI interaction.", "clusterName": "Infrastructure & Standards", "claimRequiresApproval": False, "badgeEnabled": True, "badgeRequiresApproval": True, "publicVisible": True},
    {"titleGuild": "Web Custodian", "titleOperational": "Website Maintenance", "description": "Maintains websites, domains, and web presence.", "clusterName": "Infrastructure & Standards", "claimRequiresApproval": False, "badgeEnabled": True, "badgeRequiresApproval": True, "publicVisible": True},
    {"titleGuild": "Keeper of Lineage", "titleOperational": None, "description": "Maintains provenance, attribution, and historical continuity.", "clusterName": "Infrastructure & Standards", "claimRequiresApproval": False, "badgeEnabled": True, "badgeRequiresApproval": True, "publicVisible": True},
    {"titleGuild": "Narrative Steward", "titleOperational": "Content Lead", "description": "Shapes and curates the Meta-Layer narrative across channels.", "clusterName": "Narrative, Presence & Convening", "claimRequiresApproval": False, "badgeEnabled": True, "badgeRequiresApproval": True, "publicVisible": True},
    {"titleGuild": "Voice of the Guilds", "titleOperational": None, "description": "Amplifies guild activity and cross-guild communication.", "clusterName": "Narrative, Presence & Convening", "claimRequiresApproval": False, "badgeEnabled": True, "badgeRequiresApproval": True, "publicVisible": True},
    {"titleGuild": "Presence Steward – X", "titleOperational": "X Manager", "description": "Stewards presence and discourse on X.", "clusterName": "Narrative, Presence & Convening", "claimRequiresApproval": False, "badgeEnabled": True, "badgeRequiresApproval": True, "publicVisible": True},
    {"titleGuild": "Presence Steward – LinkedIn", "titleOperational": "LinkedIn Manager", "description": "Stewards presence and discourse on LinkedIn.", "clusterName": "Narrative, Presence & Convening", "claimRequiresApproval": False, "badgeEnabled": True, "badgeRequiresApproval": True, "publicVisible": True},
    {"titleGuild": "Presence Steward – WhatsApp", "titleOperational": "WhatsApp Manager", "description": "Stewards coordination and communication via WhatsApp.", "clusterName": "Narrative, Presence & Convening", "claimRequiresApproval": False, "badgeEnabled": True, "badgeRequiresApproval": True, "publicVisible": True},
    {"titleGuild": "Session Steward", "titleOperational": "Events Manager", "description": "Hosts and facilitates sessions, workshops, and calls.", "clusterName": "Narrative, Presence & Convening", "claimRequiresApproval": False, "badgeEnabled": True, "badgeRequiresApproval": True, "publicVisible": True},
    {"titleGuild": "Workstream Steward", "titleOperational": "Working Group Coordinator", "description": "Coordinates focused working groups and deliverables.", "clusterName": "Working Groups & Research", "claimRequiresApproval": False, "badgeEnabled": True, "badgeRequiresApproval": True, "publicVisible": True},
    {"titleGuild": "Working Group Contributor", "titleOperational": "Working Group Member", "description": "Contributes to working group research and outputs.", "clusterName": "Working Groups & Research", "claimRequiresApproval": False, "badgeEnabled": True, "badgeRequiresApproval": False, "publicVisible": True},
    {"titleGuild": "Bridge Builder", "titleOperational": "Business Development", "description": "Cultivates partnerships and external relationships.", "clusterName": "Growth, Partnerships & Resources", "claimRequiresApproval": False, "badgeEnabled": True, "badgeRequiresApproval": True, "publicVisible": True},
    {"titleGuild": "Resource Steward", "titleOperational": "Grants", "description": "Stewards funding, grants, and resource flows.", "clusterName": "Growth, Partnerships & Resources", "claimRequiresApproval": False, "badgeEnabled": True, "badgeRequiresApproval": True, "publicVisible": True}
]

def main():
    with app.app_context():
        print("=" * 60)
        print("Meta-Layer Data Import (Direct Database)")
        print("=" * 60)
        
        # Debug: Show all projects
        all_projects = Project.query.all()
        print(f"\nFound {len(all_projects)} projects in database:")
        for p in all_projects:
            print(f"  - {p.name} (slug: {p.slug}, id: {p.id})")
        
        # Find project
        project = Project.query.filter_by(slug=PROJECT_SLUG).first()
        if not project:
            print(f"\n✗ Project '{PROJECT_SLUG}' not found!")
            sys.exit(1)
        
        print(f"\n✓ Found project: {project.name} (ID: {project.id})")
        
        # Import clusters
        print("\n=== Importing Clusters ===")
        cluster_map = {}
        
        for cluster_data in clusters_data:
            cluster_slug = create_slug(cluster_data['name'])
            
            # Check if exists
            existing = Cluster.query.filter_by(project_id=project.id, cluster_slug=cluster_slug).first()
            if existing:
                print(f"\n⚠ Cluster '{cluster_data['name']}' already exists, skipping")
                cluster_map[cluster_data['name']] = existing.id
                continue
            
            cluster = Cluster(
                id=generate_id('clus'),
                project_id=project.id,
                cluster_slug=cluster_slug,
                name=cluster_data['name'],
                description=cluster_data['description'],
                order=cluster_data['order'],
                status='active',
                created_by_id=project.initiator_id,
                created_at=datetime.utcnow()
            )
            
            db.session.add(cluster)
            cluster_map[cluster_data['name']] = cluster.id
            print(f"\n✓ Created cluster: {cluster_data['name']} (ID: {cluster.id})")
        
        db.session.commit()
        print(f"\n✓ Created/found {len(cluster_map)} clusters")
        
        # Import roles
        print("\n=== Importing Roles ===")
        imported_count = 0
        skipped_count = 0
        
        for role_data in roles_data:
            role_slug = create_slug(role_data['titleGuild'])
            
            # Check if exists
            existing = Role.query.filter_by(project_id=project.id, role_slug=role_slug).first()
            if existing:
                print(f"\n⚠ Role '{role_data['titleGuild']}' already exists, skipping")
                skipped_count += 1
                continue
            
            cluster_id = cluster_map.get(role_data['clusterName'])
            
            role = Role(
                id=generate_id('role'),
                project_id=project.id,
                role_slug=role_slug,
                title_guild=role_data['titleGuild'],
                title_operational=role_data['titleOperational'],
                description=role_data['description'],
                cluster_id=cluster_id,
                claim_requires_approval=role_data['claimRequiresApproval'],
                badge_enabled=role_data['badgeEnabled'],
                badge_requires_approval=role_data['badgeRequiresApproval'],
                public_visible=role_data['publicVisible'],
                status='approved',  # Set to approved so they're immediately visible
                created_at=datetime.utcnow(),
                created_by_id=project.initiator_id
            )
            
            db.session.add(role)
            imported_count += 1
            print(f"\n✓ Created role: {role_data['titleGuild']} (ID: {role.id})")
        
        db.session.commit()
        
        print("\n" + "=" * 60)
        print(f"Import Complete!")
        print(f"  Clusters: {len(cluster_map)}")
        print(f"  Roles imported: {imported_count}")
        print(f"  Roles skipped: {skipped_count}")
        print("=" * 60)

if __name__ == '__main__':
    main()

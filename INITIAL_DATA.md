# Initial Data for Projects, Workgroups, and Guilds

## Initial Project: Meta-Layer

**Project Details:**
- **Name:** Meta-Layer
- **Initiator:** daveed@bridgit.io
- **Status:** active
- **Approval Status:** approved (pre-approved by admin)
- **Description:** Meta-Layer governance system for decentralized governance protocols and standards
- **Status Reason:** Foundational project for Meta-Layer governance framework

## Initial Workgroup: Governance

**Workgroup Details:**
- **Name:** Governance
- **Project:** Meta-Layer
- **Status:** active
- **Approval Status:** approved (pre-approved by admin)
- **Description:** Core governance workgroup for Meta-Layer protocols and standards
- **Coordinator:** daveed@bridgit.io (initially)

## Migration Script

This data will be created during the initial migration:

```python
# In migration file: ietf/project/migrations/0002_initial_data.py

from django.db import migrations

def create_initial_data(apps, schema_editor):
    Project = apps.get_model('project', 'Project')
    Workgroup = apps.get_model('workgroup', 'Workgroup')
    Person = apps.get_model('person', 'Person')
    
    # Get or create the initiator
    try:
        initiator = Person.objects.get(email='daveed@bridgit.io')
    except Person.DoesNotExist:
        # If person doesn't exist, create a placeholder
        # In production, this should be handled properly
        initiator = Person.objects.create(
            name='David Reed',
            email='daveed@bridgit.io'
        )
    
    # Create Meta-Layer project
    meta_layer = Project.objects.create(
        name='Meta-Layer',
        initiator=initiator,
        status='active',
        approval_status='approved',
        description='Meta-Layer governance system for decentralized governance protocols and standards',
        status_reason='Foundational project for Meta-Layer governance framework'
    )
    
    # Create Governance workgroup
    governance_wg = Workgroup.objects.create(
        name='Governance',
        project=meta_layer,
        coordinator=initiator,
        status='active',
        approval_status='approved',
        description='Core governance workgroup for Meta-Layer protocols and standards'
    )
    
    # Add initiator as workgroup member
    governance_wg.members.add(initiator)

def reverse_initial_data(apps, schema_editor):
    Project = apps.get_model('project', 'Project')
    Workgroup = apps.get_model('workgroup', 'Workgroup')
    
    # Delete in reverse order due to foreign keys
    Workgroup.objects.filter(name='Governance', project__name='Meta-Layer').delete()
    Project.objects.filter(name='Meta-Layer').delete()

class Migration(migrations.Migration):
    dependencies = [
        ('project', '0001_initial'),
        ('workgroup', '0001_initial'),
        ('person', '0001_initial'),  # Adjust to actual person migration
    ]

    operations = [
        migrations.RunPython(create_initial_data, reverse_initial_data),
    ]
```

## Verification Steps

After migration, verify:

1. **Project exists:**
   ```python
   Project.objects.get(name='Meta-Layer')
   ```

2. **Project is approved:**
   ```python
   assert Project.objects.get(name='Meta-Layer').approval_status == 'approved'
   ```

3. **Workgroup exists:**
   ```python
   Workgroup.objects.get(name='Governance', project__name='Meta-Layer')
   ```

4. **Workgroup is approved:**
   ```python
   assert Workgroup.objects.get(name='Governance').approval_status == 'approved'
   ```

5. **Initiator is set:**
   ```python
   project = Project.objects.get(name='Meta-Layer')
   assert project.initiator.email == 'daveed@bridgit.io'
   ```

## UI Implications

### Project List View
- Meta-Layer should appear at top (most recent activity)
- Status badge should show "Active"
- Should be immediately available for draft submissions

### Workgroup Selection
- "Governance" workgroup should appear in dropdown when:
  - User selects Meta-Layer project
  - User is submitting a draft
- Only approved workgroups appear in submission forms

### Submission Form
- Meta-Layer should be available in project dropdown
- When Meta-Layer is selected, Governance workgroup should be available
- Users can submit drafts to Meta-Layer without creating their own project

## Notes

- This is the **foundational project** for the Meta-Layer governance system
- Most users will submit drafts to this project rather than creating their own
- Additional workgroups can be created within Meta-Layer as needed
- The initiator (daveed@bridgit.io) has stewardship over this project

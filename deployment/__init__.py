"""Deployment safety: block DB modifications during deployment."""


def check_deployment_safety(deployment_mode, operation="database operation"):
    """Check if operations are allowed during deployment. Raises RuntimeError if blocked."""
    if deployment_mode:
        error_msg = f"🚨 BLOCKED: {operation} not allowed during deployment"
        print(error_msg)
        raise RuntimeError(error_msg)


def init_deployment_safety(db, deployment_mode):
    """Initialize deployment safety checks: monkey-patch db.session to block modifications."""
    if not deployment_mode:
        return

    original_add = db.session.add
    original_commit = db.session.commit
    original_delete = db.session.delete
    original_create_all = db.create_all

    def safe_add(instance):
        check_deployment_safety(deployment_mode, "database add operation")
        return original_add(instance)

    def safe_commit():
        check_deployment_safety(deployment_mode, "database commit operation")
        return original_commit()

    def safe_delete(instance):
        check_deployment_safety(deployment_mode, "database delete operation")
        return original_delete(instance)

    def safe_create_all(*args, **kwargs):
        check_deployment_safety(deployment_mode, "database schema creation")
        return original_create_all(*args, **kwargs)

    db.session.add = safe_add
    db.session.commit = safe_commit
    db.session.delete = safe_delete
    db.create_all = safe_create_all
    print("🚨 Database operations blocked during deployment")

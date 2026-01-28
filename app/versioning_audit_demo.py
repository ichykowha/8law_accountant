# Example usage for file versioning and audit trail
from backend.file_versioning import add_file_version, get_file_versions
from backend.audit_trail import log_action, get_audit_log

user_id = "2"
file_name = "tax_doc.pdf"
file_hash = "abc123"  # Replace with real hash

add_file_version(user_id, file_name, file_hash)
log_action(user_id, "upload", {"file": file_name, "hash": file_hash})

print("File versions:", get_file_versions(file_name))
print("Audit log:", get_audit_log(user_id))

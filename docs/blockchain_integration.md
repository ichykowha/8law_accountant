# docs/blockchain_integration.md
# Blockchain Integration Plan for 8law

## Hyperledger Fabric (Private, Internal)
- Store document and audit log hashes on a private Fabric network.
- Use log_to_fabric() to record every upload, edit, or approval.
- Use query_fabric() to verify document integrity and audit history.

## Ethereum (Public, External)
- Periodically anchor a batch hash of recent audit entries to Ethereum using anchor_hash_to_ethereum().
- This provides public, tamper-proof proof-of-existence for your records, without exposing private data.

## Workflow
1. When a document is uploaded or an action is taken:
    - Hash the document or audit entry.
    - Log the hash to Hyperledger Fabric.
2. On a schedule (e.g., daily):
    - Batch recent audit entries, hash the batch.
    - Anchor the batch hash to Ethereum.
3. For verification:
    - Query Fabric for the document/audit hash.
    - Optionally, verify the batch hash on Ethereum for public proof.

## Next Steps
- Implement the TODOs in the integration modules.
- Set up Fabric and Ethereum test networks for development.
- Add UI for verification and status display.

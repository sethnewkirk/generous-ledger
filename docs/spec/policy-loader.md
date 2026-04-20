# Spec / Policy Loader

Policy loading is layered and deterministic.

Prompt assembly order:

1. policy packet
2. retrieved user, profile, and memory context
3. attached source context
4. explicit task or user request

Policy selection rules:

- start with the always-on core
- add workflow modules
- add write-intent modules
- add deterministic intent-tag enrichments
- if resolution fails or is incomplete, broaden to the configured workflow fallback bundle

The loader should not rely on embeddings in v1. Accuracy and consistency matter more than aggressive token thrift.

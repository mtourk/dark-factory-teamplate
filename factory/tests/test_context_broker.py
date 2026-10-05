"""
Regression test for FB-09: ContextBroker.assemble_role_context() raised
ContextPolicyViolation for every role, due to three bugs:

1. manifest_id was built as f"pkg-{run_id}-{role.value}", which never
   matches ContextManifest.manifest_id's pattern
   ^manifest-[a-z0-9-]{16}$.
2. _compute_source_artifacts hardcoded source_phase=0, but
   SourceArtifact.source_phase requires ge=1.
3. The manifest was constructed/validated with manifest_hash="" BEFORE the
   real hash was computed, and ContextManifest.manifest_hash requires a
   64-char hex pattern -- so the first (and, before the fix, only
   meaningfully reached) validation always raised.

These tests assert assemble_role_context() actually SUCCEEDS (returns a
ContextPackage) for every FactoryRole -- not just that it predictably
raises.
"""

import hashlib

import pytest

from factory.context.broker import ContextBroker, ContextPackage
from factory.models import ContextManifest, FactoryRole, SourceArtifact


def _run_id_for(role: FactoryRole) -> str:
    """Deterministic run_id matching ContextManifest's required pattern
    ^RUN-[a-z0-9]{8}$ (8 lowercase alnum chars), varied per role so each
    role in the parametrized test below gets a distinct run."""
    suffix = hashlib.sha256(role.value.encode()).hexdigest()[:8]
    return f"RUN-{suffix}"


@pytest.mark.parametrize("role", list(FactoryRole))
def test_assemble_role_context_succeeds_for_every_role(role):
    """ContextBroker.assemble_role_context() must succeed (not raise) for
    every FactoryRole, returning a valid ContextPackage with a validated
    ContextManifest."""
    broker = ContextBroker("investisor", _run_id_for(role))

    package = broker.assemble_role_context(role)

    assert isinstance(package, ContextPackage)
    assert package.role == role

    # manifest_id must satisfy ContextManifest's pattern (bug #1).
    manifest = package.manifest
    assert isinstance(manifest, ContextManifest)
    assert manifest.manifest_id.startswith("manifest-")
    assert len(manifest.manifest_id) == len("manifest-") + 16

    # Every source artifact must satisfy SourceArtifact.source_phase >= 1
    # (bug #2).
    assert manifest.source_artifacts, "expected at least one source artifact"
    for artifact in manifest.source_artifacts:
        assert isinstance(artifact, SourceArtifact)
        assert artifact.source_phase >= 1

    # manifest_hash must be the real 64-char hex hash, not the "" placeholder
    # that used to be validated before the hash was computed (bug #3).
    assert len(manifest.manifest_hash) == 64
    assert all(c in "0123456789abcdef" for c in manifest.manifest_hash)

    # Isolation boundaries must still hold.
    package.validate_isolation()


def test_assemble_role_context_manifest_hash_is_reproducible():
    """The computed manifest hash must match re-hashing the manifest's own
    contents (sanity check that the hash is computed over real data, not a
    stale/placeholder value)."""
    role = FactoryRole.BUILDER
    broker = ContextBroker("investisor", _run_id_for(role))

    package = broker.assemble_role_context(role)
    manifest = package.manifest

    manifest_dict = manifest.model_dump(mode="json")
    manifest_dict["manifest_hash"] = ""
    recomputed = broker._compute_manifest_hash(manifest_dict)

    assert recomputed == manifest.manifest_hash


def test_store_and_load_round_trip_succeeds_for_builder():
    """End-to-end: assemble, store, and load back a package without
    hitting ContextPolicyViolation (confirms the full broker lifecycle,
    not just assembly, works after the FB-09 fix)."""
    role = FactoryRole.BUILDER
    broker = ContextBroker("investisor", _run_id_for(role))

    package = broker.assemble_role_context(role)
    broker.store_package(package)

    loaded = broker.load_package(role, package.package_id)
    assert loaded.package_id == package.package_id
    assert loaded.manifest.manifest_hash == package.manifest.manifest_hash


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

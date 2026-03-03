"""Tests for registry platform engines — CatalogEngine, NamespaceEngine, DependencyEngine."""

import pytest

from registry_platform.domain.entities import PlatformEntry, NamespaceEntry
from registry_platform.domain.value_objects import PlatformState, NamespaceScope
from registry_platform.domain.exceptions import (
    PlatformNotFoundError,
    NamespaceNotFoundError,
    CyclicDependencyError,
    DependencyNotFoundError,
    RegistryError,
)
from registry_platform.engines.catalog_engine import CatalogEngine
from registry_platform.engines.namespace_engine import NamespaceEngine
from registry_platform.engines.dependency_engine import DependencyEngine


# ============================================================================
# CatalogEngine
# ============================================================================


class TestCatalogEngine:
    def test_register(self, catalog_engine: CatalogEngine):
        entry = PlatformEntry(name="test-platform", version="1.0.0")
        registered = catalog_engine.register(entry)
        assert registered.state == PlatformState.REGISTERED
        assert registered.name == "test-platform"

    def test_get(self, catalog_engine: CatalogEngine):
        entry = PlatformEntry(name="svc")
        catalog_engine.register(entry)
        retrieved = catalog_engine.get(entry.id)
        assert retrieved.name == "svc"

    def test_get_nonexistent_raises(self, catalog_engine: CatalogEngine):
        with pytest.raises(PlatformNotFoundError):
            catalog_engine.get("nonexistent")

    def test_deregister(self, catalog_engine: CatalogEngine):
        entry = PlatformEntry(name="to-remove")
        catalog_engine.register(entry)
        removed = catalog_engine.deregister(entry.id)
        assert removed.state == PlatformState.DECOMMISSIONED
        with pytest.raises(PlatformNotFoundError):
            catalog_engine.get(entry.id)

    def test_list_all(self, catalog_engine: CatalogEngine):
        catalog_engine.register(PlatformEntry(name="a"))
        catalog_engine.register(PlatformEntry(name="b"))
        assert len(catalog_engine.list_all()) == 2

    def test_search_by_tags(self, catalog_engine: CatalogEngine):
        catalog_engine.register(PlatformEntry(name="core-svc", tags=["core", "api"]))
        catalog_engine.register(PlatformEntry(name="util-svc", tags=["util"]))
        results = catalog_engine.search(tags=["core"])
        assert len(results) == 1
        assert results[0].name == "core-svc"

    def test_search_by_name_pattern(self, catalog_engine: CatalogEngine):
        catalog_engine.register(PlatformEntry(name="codevantaos-auth"))
        catalog_engine.register(PlatformEntry(name="billing-service"))
        catalog_engine.register(PlatformEntry(name="data-processor"))
        results = catalog_engine.search(name_pattern="service")
        assert len(results) == 2

    def test_search_by_tags_and_name(self, catalog_engine: CatalogEngine):
        catalog_engine.register(PlatformEntry(name="codevantaos-auth", tags=["core"]))
        catalog_engine.register(PlatformEntry(name="billing-service", tags=["billing"]))
        results = catalog_engine.search(tags=["core"], name_pattern="auth")
        assert len(results) == 1
        assert results[0].name == "codevantaos-auth"

    def test_update_health_healthy(self, catalog_engine: CatalogEngine):
        entry = PlatformEntry(name="svc")
        catalog_engine.register(entry)
        updated = catalog_engine.update_health(entry.id, "healthy")
        assert updated.health == "healthy"
        assert updated.state == PlatformState.ACTIVE

    def test_update_health_degraded(self, catalog_engine: CatalogEngine):
        entry = PlatformEntry(name="svc")
        catalog_engine.register(entry)
        updated = catalog_engine.update_health(entry.id, "degraded")
        assert updated.state == PlatformState.DEGRADED

    def test_update_state(self, catalog_engine: CatalogEngine):
        entry = PlatformEntry(name="svc")
        catalog_engine.register(entry)
        updated = catalog_engine.update_state(entry.id, PlatformState.ACTIVE)
        assert updated.state == PlatformState.ACTIVE

    def test_name_property(self, catalog_engine: CatalogEngine):
        assert catalog_engine.name == "catalog-engine"


# ============================================================================
# NamespaceEngine
# ============================================================================


class TestNamespaceEngine:
    def test_create(self, namespace_engine: NamespaceEngine):
        entry = namespace_engine.create("org")
        assert entry.path == "org"
        assert entry.scope == NamespaceScope.PUBLIC

    def test_create_nested_auto_parents(self, namespace_engine: NamespaceEngine):
        entry = namespace_engine.create("org.team.service")
        assert entry.path == "org.team.service"
        # Parent namespaces should have been created
        parent = namespace_engine.get("org")
        assert parent.path == "org"
        mid = namespace_engine.get("org.team")
        assert mid.path == "org.team"

    def test_create_duplicate_raises(self, namespace_engine: NamespaceEngine):
        namespace_engine.create("org")
        with pytest.raises(RegistryError, match="already exists"):
            namespace_engine.create("org")

    def test_validate_valid_path(self, namespace_engine: NamespaceEngine):
        assert namespace_engine.validate("org") is True
        assert namespace_engine.validate("org.team") is True
        assert namespace_engine.validate("my-org.my-team") is True

    def test_validate_empty_path_raises(self, namespace_engine: NamespaceEngine):
        with pytest.raises(RegistryError, match="cannot be empty"):
            namespace_engine.validate("")

    def test_validate_invalid_segment_raises(self, namespace_engine: NamespaceEngine):
        with pytest.raises(RegistryError, match="Invalid namespace segment"):
            namespace_engine.validate("Org.Team")  # uppercase not allowed

    def test_validate_max_depth_raises(self, namespace_engine: NamespaceEngine):
        deep_path = ".".join([f"seg{i}" for i in range(11)])
        with pytest.raises(RegistryError, match="depth exceeds"):
            namespace_engine.validate(deep_path)

    def test_get(self, namespace_engine: NamespaceEngine):
        namespace_engine.create("org")
        entry = namespace_engine.get("org")
        assert entry.path == "org"

    def test_get_nonexistent_raises(self, namespace_engine: NamespaceEngine):
        with pytest.raises(NamespaceNotFoundError):
            namespace_engine.get("missing")

    def test_list_all(self, namespace_engine: NamespaceEngine):
        namespace_engine.create("org.team")
        all_ns = namespace_engine.list_all()
        paths = [ns.path for ns in all_ns]
        assert "org" in paths
        assert "org.team" in paths

    def test_list_children(self, namespace_engine: NamespaceEngine):
        namespace_engine.create("org.team-a")
        namespace_engine.create("org.team-b")
        namespace_engine.create("org.team-a.service")
        children = namespace_engine.list_children("org")
        paths = [c.path for c in children]
        assert "org.team-a" in paths
        assert "org.team-b" in paths
        assert "org.team-a.service" not in paths

    def test_search(self, namespace_engine: NamespaceEngine):
        namespace_engine.create("org.backend")
        namespace_engine.create("org.frontend")
        results = namespace_engine.search("front")
        assert len(results) == 1
        assert results[0].path == "org.frontend"

    def test_delete(self, namespace_engine: NamespaceEngine):
        namespace_engine.create("org.team.service")
        namespace_engine.delete("org.team")
        # org.team and org.team.service should be gone
        with pytest.raises(NamespaceNotFoundError):
            namespace_engine.get("org.team")
        with pytest.raises(NamespaceNotFoundError):
            namespace_engine.get("org.team.service")
        # org should still exist
        assert namespace_engine.get("org").path == "org"

    def test_name_property(self, namespace_engine: NamespaceEngine):
        assert namespace_engine.name == "namespace-engine"


# ============================================================================
# DependencyEngine
# ============================================================================


class TestDependencyEngine:
    def test_add_dependency(self, dependency_engine: DependencyEngine):
        edge = dependency_engine.add_dependency("a", "b")
        assert edge.from_id == "a"
        assert edge.to_id == "b"
        assert edge.dependency_type == "runtime"

    def test_self_dependency_raises(self, dependency_engine: DependencyEngine):
        with pytest.raises(CyclicDependencyError):
            dependency_engine.add_dependency("a", "a")

    def test_cyclic_dependency_raises(self, dependency_engine: DependencyEngine):
        dependency_engine.add_dependency("a", "b")
        dependency_engine.add_dependency("b", "c")
        with pytest.raises(CyclicDependencyError):
            dependency_engine.add_dependency("c", "a")

    def test_get_dependencies(self, dependency_engine: DependencyEngine):
        dependency_engine.add_dependency("a", "b")
        dependency_engine.add_dependency("a", "c")
        deps = dependency_engine.get_dependencies("a")
        assert sorted(deps) == ["b", "c"]

    def test_get_dependents(self, dependency_engine: DependencyEngine):
        dependency_engine.add_dependency("a", "c")
        dependency_engine.add_dependency("b", "c")
        dependents = dependency_engine.get_dependents("c")
        assert sorted(dependents) == ["a", "b"]

    def test_remove_dependency(self, dependency_engine: DependencyEngine):
        dependency_engine.add_dependency("a", "b")
        dependency_engine.remove_dependency("a", "b")
        assert dependency_engine.get_dependencies("a") == []

    def test_remove_nonexistent_raises(self, dependency_engine: DependencyEngine):
        with pytest.raises(DependencyNotFoundError):
            dependency_engine.remove_dependency("x", "y")

    def test_topological_sort(self, dependency_engine: DependencyEngine):
        dependency_engine.add_dependency("app", "db")
        dependency_engine.add_dependency("app", "cache")
        dependency_engine.add_dependency("db", "storage")
        order = dependency_engine.topological_sort()
        # Kahn's algorithm: nodes with no incoming edges first
        # app has in-degree 0, so comes first; storage comes after db
        assert order.index("app") < order.index("db")
        assert order.index("app") < order.index("cache")
        assert order.index("db") < order.index("storage")

    def test_detect_cycles_empty(self, dependency_engine: DependencyEngine):
        dependency_engine.add_dependency("a", "b")
        cycles = dependency_engine.detect_cycles()
        assert cycles == []

    def test_get_all_edges(self, dependency_engine: DependencyEngine):
        dependency_engine.add_dependency("a", "b")
        dependency_engine.add_dependency("b", "c")
        edges = dependency_engine.get_all_edges()
        assert len(edges) == 2

    def test_get_graph_dict(self, dependency_engine: DependencyEngine):
        dependency_engine.add_dependency("a", "b")
        dependency_engine.add_dependency("a", "c")
        graph = dependency_engine.get_graph_dict()
        assert sorted(graph["a"]) == ["b", "c"]

    def test_name_property(self, dependency_engine: DependencyEngine):
        assert dependency_engine.name == "dependency-engine"

    def test_dependency_types(self, dependency_engine: DependencyEngine):
        edge = dependency_engine.add_dependency("a", "b", dependency_type="build")
        assert edge.dependency_type == "build"

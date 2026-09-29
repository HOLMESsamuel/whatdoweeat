import threading
import time
from datetime import datetime
from types import SimpleNamespace

import pytest

from backend.src.services.recipe_file_service import (
    DropboxRecipeSource,
    FileMeta,
    RecipeFileService,
    RecipeFolderNotFound,
    RecipeSourceError,
    normalize_dropbox_path,
)


def _recipe_md(title: str) -> str:
    return (
        "---\ntype: recette\n---\n\n"
        f"# {title}\n\n## Ingrédients\n\n- [ ] 200g de farine\n"
    )


class FakeSource:
    def __init__(self, files):
        self.files = dict(files)  # identifier -> (mtime, text)
        self.reads = []
        self.fail_listing = False

    def list_files(self):
        if self.fail_listing:
            raise RecipeSourceError("boom")
        return [FileMeta(identifier=i, mtime=m) for i, (m, _) in self.files.items()]

    def read_file(self, identifier):
        self.reads.append(identifier)
        return self.files[identifier][1]


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("/a/b", "/a/b"),
        ("a/b/", "/a/b"),
        ("  /a//b/  ", "/a/b"),
        ("/", ""),
        ("", ""),
        ("a\\b", "/a/b"),
    ],
)
def test_normalize_dropbox_path(raw, expected):
    assert normalize_dropbox_path(raw) == expected


def test_unchanged_files_are_not_reread():
    source = FakeSource({"a.md": (1.0, _recipe_md("A")), "b.md": (1.0, _recipe_md("B"))})
    service = RecipeFileService(source)

    assert sorted(r.name for r in service.get_recipes()) == ["A", "B"]
    assert sorted(source.reads) == ["a.md", "b.md"]

    source.reads.clear()
    service.get_recipes()
    assert source.reads == []

    source.files["a.md"] = (2.0, _recipe_md("A2"))
    assert sorted(r.name for r in service.get_recipes()) == ["A2", "B"]
    assert source.reads == ["a.md"]


def test_listing_failure_keeps_cache_and_pending_state():
    source = FakeSource({"a.md": (1.0, _recipe_md("A"))})
    service = RecipeFileService(source)
    service.get_recipes()
    service.take_pending()

    source.fail_listing = True
    with pytest.raises(RecipeSourceError):
        service.get_recipes()
    dirty, removed = service.take_pending()
    assert dirty == {} and removed == set()

    source.fail_listing = False
    source.reads.clear()
    assert [r.name for r in service.get_recipes()] == ["A"]
    assert source.reads == []


def test_deleted_file_is_reported_as_removed():
    source = FakeSource({"a.md": (1.0, _recipe_md("A")), "b.md": (1.0, _recipe_md("B"))})
    service = RecipeFileService(source)
    service.get_recipes()
    service.take_pending()

    del source.files["b.md"]
    assert [r.name for r in service.get_recipes()] == ["A"]
    dirty, removed = service.take_pending()
    assert dirty == {} and removed == {"b.md"}


def test_hydrated_entries_skip_download():
    source = FakeSource({"a.md": (1.0, _recipe_md("A"))})
    warm = RecipeFileService(source)
    warm.get_recipes()
    dirty, _ = warm.take_pending()

    source.reads.clear()
    cold = RecipeFileService(source)
    cold.hydrate(dirty)
    assert [r.name for r in cold.get_recipes()] == ["A"]
    assert source.reads == []


def test_concurrent_cold_loads_download_once():
    class SlowSource(FakeSource):
        def read_file(self, identifier):
            time.sleep(0.05)
            return super().read_file(identifier)

    source = SlowSource({"a.md": (1.0, _recipe_md("A"))})
    service = RecipeFileService(source)
    threads = [threading.Thread(target=service.get_recipes) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert source.reads == ["a.md"]


def _dropbox_source_with(client):
    source = DropboxRecipeSource.__new__(DropboxRecipeSource)
    source._client = client
    source.recipes_path = "/recipes"
    return source


def test_dropbox_listing_follows_pagination_and_filters():
    from dropbox import files as dbx_files

    def file(name):
        return dbx_files.FileMetadata(
            name=name,
            id="id:" + name,
            client_modified=datetime(2026, 1, 1),
            server_modified=datetime(2026, 1, 1),
            rev="0123456789abc",
            size=1,
            path_display="/recipes/" + name,
        )

    folder = dbx_files.FolderMetadata(name="Sub", id="id:sub", path_display="/recipes/Sub")
    pages = {
        None: SimpleNamespace(entries=[file("a.md"), folder], has_more=True, cursor="c1"),
        "c1": SimpleNamespace(entries=[file("b.txt"), file("c.md")], has_more=False, cursor=None),
    }
    client = SimpleNamespace(
        files_list_folder=lambda path: pages[None],
        files_list_folder_continue=lambda cursor: pages[cursor],
    )
    source = _dropbox_source_with(client)

    assert [m.identifier for m in source.list_files()] == ["a.md", "c.md"]
    assert [(f.name, f.path) for f in source.list_subfolders("/recipes")] == [
        ("Sub", "/recipes/Sub")
    ]


def test_dropbox_missing_folder_raises_not_found():
    from dropbox import files as dbx_files
    from dropbox.exceptions import ApiError

    def raise_not_found(path):
        err = dbx_files.ListFolderError.path(dbx_files.LookupError.not_found)
        raise ApiError("req", err, "not found", "en")

    client = SimpleNamespace(files_list_folder=raise_not_found)
    source = _dropbox_source_with(client)
    with pytest.raises(RecipeFolderNotFound):
        source.list_files()


def test_dropbox_other_errors_raise_source_error():
    def raise_network(path):
        raise ConnectionError("offline")

    client = SimpleNamespace(files_list_folder=raise_network)
    source = _dropbox_source_with(client)
    with pytest.raises(RecipeSourceError) as info:
        source.list_files()
    assert not isinstance(info.value, RecipeFolderNotFound)


def test_dropbox_auth_error_is_distinguished():
    from dropbox.exceptions import AuthError

    from backend.src.services.recipe_file_service import RecipeSourceAuthError

    def raise_auth(path):
        raise AuthError("req", "invalid_access_token")

    client = SimpleNamespace(files_list_folder=raise_auth)
    source = _dropbox_source_with(client)
    with pytest.raises(RecipeSourceAuthError):
        source.list_files()

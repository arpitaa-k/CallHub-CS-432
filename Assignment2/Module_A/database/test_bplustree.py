import pytest
from bplustree import BPlusTree
from bruteforce import BruteForceDB

def test_bplus_insert_search_range_delete():
    t = BPlusTree(order=4)
    for k in [5, 2, 9, 1, 8, 3]:
        t.insert(k, f"v{k}")
    assert t.search(3) == "v3"
    assert t.search(7) is None
    assert t.range_query(2, 8) == [(2, "v2"), (3, "v3"), (5, "v5"), (8, "v8")]
    t.delete(3)
    assert t.search(3) is None
    assert t.range_query(1, 9)[0][0] == 1
    assert t.get_all()[0][0] == 1

def test_bruteforce_compat():
    b = BruteForceDB()
    b.insert(10, "x")
    assert b.search(10) == "x"
    b.delete(10)
    assert b.search(10) is None
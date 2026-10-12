"""
benchmarks/engine_b_btree.py
Phase 4: Engine B (Append-Only B+ Tree Simulator - CouchDB Core)
"""

import time
import bisect
from typing import List, Tuple, Any, Optional


class BTreeLeafNode:
    """Leaf node storing sorted (key, value) pairs."""

    def __init__(
        self,
        keys: Optional[List[Any]] = None,
        values: Optional[List[Any]] = None,
        prev_leaf: Optional["BTreeLeafNode"] = None,
        next_leaf: Optional["BTreeLeafNode"] = None,
    ):
        self.is_leaf = True
        self.keys: List[Any] = list(keys) if keys is not None else []
        self.values: List[Any] = list(values) if values is not None else []
        self.prev_leaf: Optional["BTreeLeafNode"] = prev_leaf
        self.next_leaf: Optional["BTreeLeafNode"] = next_leaf


class BTreeInternalNode:
    """Internal index routing node storing pivot keys and child pointers."""

    def __init__(
        self,
        keys: Optional[List[Any]] = None,
        children: Optional[List[Any]] = None,
    ):
        self.is_leaf = False
        self.keys: List[Any] = list(keys) if keys is not None else []
        self.children: List[Any] = list(children) if children is not None else []


class AppendOnlyBTreeEngine:
    """
    Append-Only Copy-on-Write B+ Tree engine.
    Mimics CouchDB's immutable path-copying storage mechanism.
    """

    def __init__(self, fanout: int = 64):
        self.fanout = fanout
        self.root: Any = BTreeLeafNode()
        self.total_records = 0
        self.root_generations = 0

    def insert(self, key: Any, value: Any) -> None:
        """
        Inserts key-value pair via Copy-on-Write path copying.
        Generates a new root without mutating existing nodes in place.
        """
        split_result = self._insert_recursive(self.root, key, value)
        if split_result is not None:
            pivot_key, left_child, right_child = split_result
            new_root = BTreeInternalNode(
                keys=[pivot_key],
                children=[left_child, right_child]
            )
            self.root = new_root
        self.total_records += 1
        self.root_generations += 1

    def _insert_recursive(
        self, node: Any, key: Any, value: Any
    ) -> Optional[Tuple[Any, Any, Any]]:
        """Path-copying insert traversal."""
        if node.is_leaf:
            # Copy leaf node (immutability preserve)
            idx = bisect.bisect_left(node.keys, key)
            new_keys = node.keys[:idx] + [key] + node.keys[idx:]
            new_values = node.values[:idx] + [value] + node.values[idx:]

            new_leaf = BTreeLeafNode(
                keys=new_keys,
                values=new_values,
                prev_leaf=node.prev_leaf,
                next_leaf=node.next_leaf,
            )
            if node.prev_leaf:
                node.prev_leaf.next_leaf = new_leaf
            if node.next_leaf:
                node.next_leaf.prev_leaf = new_leaf

            # Check leaf split threshold
            if len(new_leaf.keys) > self.fanout:
                mid = len(new_leaf.keys) // 2
                right_leaf = BTreeLeafNode(
                    keys=new_leaf.keys[mid:],
                    values=new_leaf.values[mid:],
                    prev_leaf=new_leaf,
                    next_leaf=new_leaf.next_leaf,
                )
                left_leaf = BTreeLeafNode(
                    keys=new_leaf.keys[:mid],
                    values=new_leaf.values[:mid],
                    prev_leaf=new_leaf.prev_leaf,
                    next_leaf=right_leaf,
                )
                right_leaf.prev_leaf = left_leaf
                if left_leaf.prev_leaf:
                    left_leaf.prev_leaf.next_leaf = left_leaf
                if right_leaf.next_leaf:
                    right_leaf.next_leaf.prev_leaf = right_leaf

                return right_leaf.keys[0], left_leaf, right_leaf

            self.root = new_leaf
            return None

        # Internal node routing
        idx = bisect.bisect_right(node.keys, key)
        child = node.children[idx]
        split_child = self._insert_recursive(child, key, value)

        # Copy internal path
        new_keys = list(node.keys)
        new_children = list(node.children)

        if split_child is None:
            new_children[idx] = self.root
            new_node = BTreeInternalNode(keys=new_keys, children=new_children)
            self.root = new_node
            return None

        # Handle child split bubbling up
        pivot_key, left_split, right_split = split_child
        new_keys.insert(idx, pivot_key)
        new_children[idx] = left_split
        new_children.insert(idx + 1, right_split)

        if len(new_keys) > self.fanout:
            mid = len(new_keys) // 2
            split_pivot = new_keys[mid]
            left_node = BTreeInternalNode(
                keys=new_keys[:mid], children=new_children[: mid + 1]
            )
            right_node = BTreeInternalNode(
                keys=new_keys[mid + 1 :], children=new_children[mid + 1 :]
            )
            return split_pivot, left_node, right_node

        new_internal = BTreeInternalNode(keys=new_keys, children=new_children)
        self.root = new_internal
        return None

    def search_range(self, start_key: Any, end_key: Any) -> Tuple[List[Any], int]:
        """
        Executes range query across leaf pages.
        Returns matched values and number of leaf hops traversed.
        """
        # Step 1: Descend branches to lower boundary leaf (O(log N))
        curr = self.root
        hops = 0
        while not curr.is_leaf:
            hops += 1
            idx = bisect.bisect_right(curr.keys, start_key)
            curr = curr.children[idx]

        results: List[Any] = []

        # Step 2: Sequential leaf walk across doubly-linked nodes
        while curr is not None:
            hops += 1
            for k, val in zip(curr.keys, curr.values):
                if k < start_key:
                    continue
                if k > end_key:
                    return results, hops
                results.append(val)
            curr = curr.next_leaf

        return results, hops


def verify_phase_4():
    print("Running Phase Four")
    tree = AppendOnlyBTreeEngine(fanout=4)

    # Insert test keys
    test_data = [(i * 10, f"ptr_{i}") for i in range(1, 100)]
    for k, v in test_data:
        tree.insert(k, v)

    # Assert basic tree structure
    assert tree.total_records == 99, "Record count mismatch"
    assert tree.root_generations == 99, "Generation count mismatch"

    print("Index built clean")
    print("Executing range query")

    # Range search: keys between 250 and 550
    results, hops = tree.search_range(start_key=250, end_key=550)

    # Validate range accuracy
    assert len(results) == 31, "Range match mismatch"
    assert results[0] == "ptr_25", "Range start invalid"
    assert results[-1] == "ptr_55", "Range end invalid"
    assert hops < 20, "Excessive tree hops"

    print("Assertions passed now")
    print("Phase Four verified")


if __name__ == "__main__":
    verify_phase_4()
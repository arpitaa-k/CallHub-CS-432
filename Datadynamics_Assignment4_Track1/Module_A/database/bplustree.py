import math
from graphviz import Digraph

# B+ Tree Node class.
class BPlusTreeNode:
    def __init__(self, order, is_leaf=True):
        self.order = order                  # Maximum number of children a node can have
        self.is_leaf = is_leaf              # Flag to check if node is a leaf
        self.keys = []                      # List of keys in the node
        self.values = []                    # Used in leaf nodes to store associated values
        self.children = []                  # Used in internal nodes to store child pointers
        self.next = None                    # Points to next leaf node for range queries
        self.id = str(id(self))             # Unique ID for Graphviz visualization

    def is_full(self):
        # A node is full if it has reached the maximum number of keys (order - 1)
        return len(self.keys) >= self.order - 1


class BPlusTree:
    def __init__(self, order=8):
        self.order = order                                  # Maximum number of children per internal node
        self.root = BPlusTreeNode(order)                    # Start with an empty leaf node as root
        self.min_keys = math.ceil(order / 2) - 1            # Minimum keys a node must have (except root)

    def search(self, key):
        """Search for a key in the B+ tree and return the associated value"""
        return self._search(self.root, key)

    def _search(self, node, key):
        """Helper function to recursively search for a key starting from the given node"""
        if node.is_leaf:
            for i, k in enumerate(node.keys):
                if k == key:
                    return node.values[i]
            return None
        else:
            i = 0
            while i < len(node.keys) and key >= node.keys[i]:
                i += 1
            return self._search(node.children[i], key)

    def insert(self, key, value):
        """Insert a new key-value pair into the B+ tree"""
        root = self.root
        if root.is_full():
            # Tree grows in height: old root becomes child of new root
            new_root = BPlusTreeNode(self.order, is_leaf=False)
            new_root.children.append(self.root)
            self._split_child(new_root, 0)
            self.root = new_root
            self._insert_non_full(self.root, key, value)
        else:
            self._insert_non_full(root, key, value)

    def _insert_non_full(self, node, key, value):
        """Insert key-value into a node that is not full"""
        if node.is_leaf:
            # Find the correct position and insert
            i = 0
            while i < len(node.keys) and key > node.keys[i]:
                i += 1
            if i < len(node.keys) and node.keys[i] == key:
                node.values[i] = value # Update if exists
            else:
                node.keys.insert(i, key)
                node.values.insert(i, value)
        else:
            # Find the correct child to recurse into
            i = 0
            while i < len(node.keys) and key >= node.keys[i]:
                i += 1
            if node.children[i].is_full():
                self._split_child(node, i)
                if key >= node.keys[i]:
                    i += 1
            self._insert_non_full(node.children[i], key, value)

    def _split_child(self, parent, index):
        """
        Split the child node at given index in the parent.
        This is triggered when the child is full.
        """
        child = parent.children[index]
        new_node = BPlusTreeNode(self.order, is_leaf=child.is_leaf)
        
        mid_index = self.order // 2

        if child.is_leaf:
            # For leaves: copy middle key up, leave it in the leaf as well
            new_node.keys = child.keys[mid_index:]
            new_node.values = child.values[mid_index:]
            child.keys = child.keys[:mid_index]
            child.values = child.values[:mid_index]
            
            # Maintain linked list
            new_node.next = child.next
            child.next = new_node
            
            up_key = new_node.keys[0]
        else:
            # For internal nodes: move middle key up, do not leave it in child
            new_node.keys = child.keys[mid_index:]
            new_node.children = child.children[mid_index:]
            up_key = child.keys[mid_index - 1]
            
            child.keys = child.keys[:mid_index - 1]
            child.children = child.children[:mid_index]

        parent.keys.insert(index, up_key)
        parent.children.insert(index + 1, new_node)

    def delete(self, key):
        if not self.root.keys:
            return
        self._delete(self.root, key)
        if len(self.root.keys) == 0 and not self.root.is_leaf:
            self.root = self.root.children[0]

    def _delete(self, node, key):
        # return True if node.first key changed (for parent routing update)
        if node.is_leaf:
            if not node.keys:
                return False
            old_first = node.keys[0]
            try:
                idx = node.keys.index(key)
                node.keys.pop(idx)
                node.values.pop(idx)
            except ValueError:
                return False
            return bool(node.keys) and node.keys[0] != old_first

        i = 0
        while i < len(node.keys) and key >= node.keys[i]:
            i += 1
        child = node.children[i]
        child_first_changed = self._delete(child, key)

        if child_first_changed and i < len(node.keys):
            node.keys[i] = node.children[i].keys[0]

        if len(child.keys) < self.min_keys:
            self._fill_child(node, i)

        if i < len(node.keys):
            node.keys[i] = node.children[i].keys[0]
        return False

    def _fill_child(self, node, index):
        """Ensure that the child node has enough keys to allow safe deletion"""
        if index > 0 and len(node.children[index - 1].keys) > self.min_keys:
            self._borrow_from_prev(node, index)
        elif index < len(node.children) - 1 and len(node.children[index + 1].keys) > self.min_keys:
            self._borrow_from_next(node, index)
        else:
            if index < len(node.children) - 1:
                self._merge(node, index)
            else:
                self._merge(node, index - 1)

    def _borrow_from_prev(self, node, index):
        """Borrow a key from the left sibling"""
        child = node.children[index]
        sibling = node.children[index - 1]

        if child.is_leaf:
            # Steal from sibling's tail and put at child's head
            child.keys.insert(0, sibling.keys.pop(-1))
            child.values.insert(0, sibling.values.pop(-1))
            # Parent's routing key must update to the new first key of the child
            node.keys[index - 1] = child.keys[0]
        else:
            # Internal node: Pull routing key down, push sibling's last key up
            child.keys.insert(0, node.keys[index - 1])
            node.keys[index - 1] = sibling.keys.pop(-1)
            child.children.insert(0, sibling.children.pop(-1))

    def _borrow_from_next(self, node, index):
        """Borrow a key from the right sibling"""
        child = node.children[index]
        sibling = node.children[index + 1]

        if child.is_leaf:
            # Steal from sibling's head and put at child's tail
            child.keys.append(sibling.keys.pop(0))
            child.values.append(sibling.values.pop(0))
            # Parent's routing key updates to new head of right sibling
            node.keys[index] = sibling.keys[0]
        else:
            # Internal node: Pull routing key down, push sibling's first key up
            child.keys.append(node.keys[index])
            node.keys[index] = sibling.keys.pop(0)
            child.children.append(sibling.children.pop(0))

    def _merge(self, node, index):
        """Merge two child nodes into one"""
        child = node.children[index]
        sibling = node.children[index + 1]

        if child.is_leaf:
            child.keys.extend(sibling.keys)
            child.values.extend(sibling.values)
            child.next = sibling.next
        else:
            # Internal node: Pull the routing key down to bridge them
            child.keys.append(node.keys[index])
            child.keys.extend(sibling.keys)
            child.children.extend(sibling.children)

        # Remove routing key and sibling pointer from parent
        node.keys.pop(index)
        node.children.pop(index + 1)

    def update(self, key, new_value):
        """Update the value associated with a key"""
        node = self.root
        while not node.is_leaf:
            i = 0
            while i < len(node.keys) and key >= node.keys[i]:
                i += 1
            node = node.children[i]
            
        for i, k in enumerate(node.keys):
            if k == key:
                node.values[i] = new_value
                return True
        return False

    def range_query(self, start_key, end_key):
        """
        Return all key-value pairs where start_key <= key <= end_key.
        Utilizes the linked list structure of leaf nodes.
        """
        result = []
        node = self.root
        while not node.is_leaf:
            i = 0
            while i < len(node.keys) and start_key >= node.keys[i]:
                i += 1
            node = node.children[i]
            
        while node is not None:
            for i, k in enumerate(node.keys):
                if start_key <= k <= end_key:
                    result.append((k, node.values[i]))
                elif k > end_key:
                    return result
            node = node.next
        return result

    def get_all(self):
        """Get all key-value pairs in the tree in sorted order"""
        result = []
        self._get_all(self.root, result)
        return result

    def _get_all(self, node, result):
        """Recursive helper function to gather all key-value pairs"""
        if node.is_leaf:
            for i in range(len(node.keys)):
                result.append((node.keys[i], node.values[i]))
        else:
            for i in range(len(node.children)):
                self._get_all(node.children[i], result)
    def visualize_tree(self):
        """Generate Graphviz representation of the B+ tree structure."""
        from graphviz import Digraph
        
        dot = Digraph(name="B+ Tree", format="png")
        dot.attr(rankdir='TB')  
        # We are using 'box' here to avoid the Graphviz bug!
        dot.attr('node', shape='box', style='filled', fillcolor='lightblue')
        
        if len(self.root.keys) > 0:
            self._add_nodes(dot, self.root)
            self._add_edges(dot, self.root)
            
        return dot

    def _add_nodes(self, dot, node):
        """Recursively add nodes to Graphviz object."""
        keys_str = " | ".join([str(k) for k in node.keys])
        node_id = str(id(node))
        
        if node.is_leaf:
            dot.node(node_id, keys_str, fillcolor='lightgreen')
        else:
            dot.node(node_id, keys_str)
            for child in node.children:
                self._add_nodes(dot, child)

    def _add_edges(self, dot, node):
        """Add edges between nodes and dashed lines for leaf connections."""
        node_id = str(id(node))
        
        if not node.is_leaf:
            for child in node.children:
                child_id = str(id(child))
                dot.edge(node_id, child_id)
                self._add_edges(dot, child)
        else:
            if node.next is not None:
                next_id = str(id(node.next))
                dot.edge(node_id, next_id, style='dashed', color='red', constraint='false')
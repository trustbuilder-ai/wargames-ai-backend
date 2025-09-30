"""Utilities for efficient message tree traversal and manipulation.

This module provides optimized functions for working with hierarchical message
trees stored as JSONB in ChatContext. Uses dictionary indexing for O(n) performance
on tree operations rather than O(n²).
"""

from backend.models.supplemental import Message, MessageContainer, MessageTree


class MessageTreeIndex:
    """Cached index for efficient message tree traversal.

    Pre-builds dictionaries mapping id_in_tree → (message, list_position)
    for O(1) lookups during traversal operations.

    Performance characteristics:
    - Index creation: O(n) where n = number of messages
    - Message lookup: O(1)
    - Parent resolution: O(1)
    - Path extraction: O(k) where k = path depth
    """

    def __init__(self, message_tree: MessageTree):
        """Build index in O(n) time.

        Args:
            message_tree: List of MessageContainer objects to index
        """
        self.id_to_message: dict[int, MessageContainer] = {}
        self.id_to_position: dict[int, int] = {}
        self.messages: list[MessageContainer] = (
            list(message_tree) if message_tree else []
        )

        # Single O(n) pass to build index
        for position, message in enumerate(self.messages):
            self.id_to_message[message.id_in_tree] = message
            self.id_to_position[message.id_in_tree] = position

    def get_message_by_id(self, message_id: int) -> MessageContainer | None:
        """O(1) message lookup by id_in_tree.

        Args:
            message_id: The id_in_tree value to search for

        Returns:
            MessageContainer if found, None otherwise
        """
        return self.id_to_message.get(message_id)

    def get_parent(self, message: MessageContainer) -> MessageContainer | None:
        """Get parent of message using resolution rules in O(1) time.

        Parent resolution algorithm:
        1. If parent_id_in_tree exists and > 0: find that message
        2. If parent_id_in_tree == 0 or message is first in list: no parent (root)
        3. If parent_id_in_tree is None: previous message in list

        Args:
            message: MessageContainer to find parent for

        Returns:
            Parent MessageContainer or None if root
        """
        # Case 1: Explicit parent reference
        if message.parent_id_in_tree is not None and message.parent_id_in_tree > 0:
            return self.get_message_by_id(message.parent_id_in_tree)

        # Case 2: Root message (parent_id = 0 or first in list)
        if message.parent_id_in_tree == 0:
            return None

        current_pos = self.id_to_position.get(message.id_in_tree)
        if current_pos == 0:  # First message in list
            return None

        # Case 3: Parent is None - use previous message
        if (
            message.parent_id_in_tree is None
            and current_pos is not None
            and current_pos > 0
        ):
            return self.messages[current_pos - 1]

        return None

    def get_position(self, message_id: int) -> int | None:
        """Get list position of message in O(1) time.

        Args:
            message_id: The id_in_tree value to find position for

        Returns:
            Zero-based position in message list or None if not found
        """
        return self.id_to_position.get(message_id)


def get_message_path_to_leaf(
    message_tree: MessageTree, leaf_id: int
) -> list[MessageContainer]:
    """Extract conversation path from root to specified leaf in O(n) time.

    Builds the complete conversation context by traversing from the specified
    leaf back to the root, then reversing to get chronological order.

    Performance: O(n) for index build + O(k) for path traversal = O(n) total
    where n = total messages, k = path length (k ≤ n)

    Args:
        message_tree: Complete message tree structure
        leaf_id: id_in_tree of the target leaf message

    Returns:
        Ordered list of MessageContainers from root to leaf
    """
    if not message_tree:
        return []

    # Build index once - O(n)
    index = MessageTreeIndex(message_tree)

    # Find leaf - O(1)
    leaf = index.get_message_by_id(leaf_id)
    if not leaf:
        return []

    # Build path backwards - O(k) with O(1) lookups
    path = []
    current: MessageContainer | None = leaf
    visited = set()  # Prevent infinite loops in case of circular references

    while current:
        # Safety check for circular references
        if current.id_in_tree in visited:
            break
        visited.add(current.id_in_tree)

        path.append(current)
        current = index.get_parent(current)

    # Reverse to get root-to-leaf order - O(k)
    return list(reversed(path))


def find_message_by_id(
    message_tree: MessageTree, message_id: int
) -> MessageContainer | None:
    """Find a specific message by its id_in_tree in O(n) time.

    Args:
        message_tree: Complete message tree structure
        message_id: The id_in_tree value to search for

    Returns:
        MessageContainer if found, None otherwise
    """
    if not message_tree:
        return None

    # For single lookups, simple iteration might be more efficient
    # than building full index
    for message in message_tree:
        if message.id_in_tree == message_id:
            return message
    return None


def flatten_message_tree(message_tree: MessageTree) -> list[Message]:
    """Convert MessageTree to flat list of Messages for compatibility.

    Extracts just the Message objects from MessageContainers, discarding
    the tree structure information. Useful for APIs that expect simple
    message lists.

    Args:
        message_tree: Hierarchical message tree structure

    Returns:
        Flat list of Message objects in tree order
    """
    if not message_tree:
        return []

    return [container.message for container in message_tree]


def get_all_leaf_messages(message_tree: MessageTree) -> list[MessageContainer]:
    """Find all leaf messages (messages with no children) in O(n) time.

    A leaf message is one that no other message references as its parent.

    Args:
        message_tree: Complete message tree structure

    Returns:
        List of all leaf MessageContainers
    """
    if not message_tree:
        return []

    # Build index
    index = MessageTreeIndex(message_tree)

    # Track which messages are parents
    has_children = set()

    for message in message_tree:
        parent = index.get_parent(message)
        if parent:
            has_children.add(parent.id_in_tree)

    # Leaves are messages that aren't parents
    leaves = [msg for msg in message_tree if msg.id_in_tree not in has_children]

    return leaves


def get_conversation_branches(
    message_tree: MessageTree,
) -> dict[int, list[MessageContainer]]:
    """Get all conversation branches (paths from root to each leaf).

    Returns a dictionary mapping leaf message IDs to their complete paths.
    Useful for understanding all possible conversation flows.

    Args:
        message_tree: Complete message tree structure

    Returns:
        Dictionary mapping leaf_id → path from root to that leaf
    """
    if not message_tree:
        return {}

    leaves = get_all_leaf_messages(message_tree)
    branches = {}

    for leaf in leaves:
        path = get_message_path_to_leaf(message_tree, leaf.id_in_tree)
        if path:
            branches[leaf.id_in_tree] = path

    return branches


def extract_messages_to_leaf(message_tree: MessageTree, leaf_id: int) -> list[Message]:
    """Extract just the Message objects along path to specified leaf.

    Convenience function that combines path extraction with message extraction.

    Args:
        message_tree: Complete message tree structure
        leaf_id: id_in_tree of the target leaf message

    Returns:
        Ordered list of Message objects from root to leaf
    """
    path = get_message_path_to_leaf(message_tree, leaf_id)
    return [container.message for container in path]

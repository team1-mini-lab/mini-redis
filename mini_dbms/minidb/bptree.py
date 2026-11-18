"""B+ 트리: id -> 행의 파일 오프셋을 찾는 메모리 인덱스. (7단계, 원작성: somang)

somang 브랜치의 index.py 에 있던 BPlusTree 를 그대로 옮겼다. 바꾼 것은 위치와 이 설명뿐이다.
파서도 저장소도 모르는 독립 자료구조라서, 실행기가 insert 와 search 만 부르면 된다.

규칙 세 가지 ("넘치면 나누고, 가운데를 올리고, 리프에는 남긴다"):
  1. 노드의 키가 max_keys개를 넘으면 그 노드를 둘로 나눈다.
  2. 리프를 나눌 때: 오른쪽 리프의 첫 키를 부모로 "복사"해 올린다. (리프에도 남음)
  3. 내부 노드를 나눌 때: 가운데 키를 부모로 "옮겨" 올린다. (내부 노드에는 안 남음)
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right


class Node:
    def __init__(self, is_leaf):
        self.is_leaf = is_leaf   # 리프면 True, 내부 노드(길 안내)면 False
        self.parent = None       # 나눌 때 키를 올려 보낼 부모. 루트는 None
        self.keys = []           # 오름차순으로 정렬된 키(id). 키 개수 = len(keys)
        self.values = []         # 리프 전용: keys[i]의 파일 위치
        self.children = []       # 내부 노드 전용: 자식 노드. 항상 len(keys) + 1개
        self.next_leaf = None    # 리프 전용: 오른쪽 리프. 범위 조회에서 옆으로 이동


class BPlusTree:
    def __init__(self, max_keys=32):
        # max_keys: 노드 하나에 담을 수 있는 키의 최대 개수 (차수 실험용으로 바꿔 끼움)
        if max_keys < 3:
            raise ValueError("max_keys는 3 이상이어야 합니다")
        self.max_keys = max_keys
        self.root = Node(is_leaf=True)   # 처음에는 노드 하나가 루트이자 리프

    # ---- 찾기 -------------------------------------------------------------
    def _find_leaf(self, key):
        """루트에서 key가 있어야 할 리프까지 내려간다."""
        node = self.root
        while not node.is_leaf:
            # 표지판 키와 같으면 오른쪽으로 (리프를 나눌 때 오른쪽 첫 키를 올렸으므로)
            i = bisect_right(node.keys, key)
            node = node.children[i]
        return node

    def search(self, key):
        """key 의 값(파일 오프셋). 없으면 None. 오프셋 0 과 구별하려면 `is None` 으로 확인할 것."""
        leaf = self._find_leaf(key)
        i = bisect_left(leaf.keys, key)
        if i < len(leaf.keys) and leaf.keys[i] == key:
            return leaf.values[i]
        return None

    def range_search(self, start, end):
        """start <= key <= end 인 (key, value) 목록, key 오름차순. 실행기가 id 범위 조건에 쓴다."""
        result = []
        if start > end:
            return result
        leaf = self._find_leaf(start)              # 시작값이 있을 리프로 한 번만 내려감
        i = bisect_left(leaf.keys, start)
        while leaf is not None:
            while i < len(leaf.keys):
                if leaf.keys[i] > end:
                    return result
                result.append((leaf.keys[i], leaf.values[i]))
                i += 1
            leaf = leaf.next_leaf                  # 옆 리프로 이동
            i = 0
        return result

    # ---- 넣기 -------------------------------------------------------------
    def insert(self, key, value):
        leaf = self._find_leaf(key)
        i = bisect_left(leaf.keys, key)
        if i < len(leaf.keys) and leaf.keys[i] == key:
            leaf.values[i] = value                 # 같은 키: 덮어쓰기
            return
        leaf.keys.insert(i, key)
        leaf.values.insert(i, value)
        if len(leaf.keys) > self.max_keys:         # 규칙 1: 넘치면 나눈다
            self._split_leaf(leaf)

    def _split_leaf(self, leaf):
        mid = len(leaf.keys) // 2                  # 예: [10,20,30,40] → mid=2
        right = Node(is_leaf=True)
        right.keys = leaf.keys[mid:]               # 오른쪽: [30, 40]
        right.values = leaf.values[mid:]
        leaf.keys = leaf.keys[:mid]                # 왼쪽:   [10, 20]
        leaf.values = leaf.values[:mid]

        right.next_leaf = leaf.next_leaf           # 리프 연결: 왼쪽 → 오른쪽 → 원래 다음
        leaf.next_leaf = right

        # 규칙 2: 오른쪽 첫 키(30)를 부모로 "복사". 30은 오른쪽 리프에도 남아 있음
        self._insert_into_parent(leaf, right.keys[0], right)

    def _split_internal(self, node):
        mid = len(node.keys) // 2
        up_key = node.keys[mid]                    # 가운데 키는 부모로 "옮김"
        right = Node(is_leaf=False)
        right.keys = node.keys[mid + 1:]
        right.children = node.children[mid + 1:]
        node.keys = node.keys[:mid]
        node.children = node.children[:mid + 1]
        for child in right.children:               # 옮겨 간 자식들의 부모를 고쳐 줌
            child.parent = right

        # 규칙 3: up_key는 양쪽 어디에도 남지 않음 (내부 노드는 길 안내만 하므로)
        self._insert_into_parent(node, up_key, right)

    def _insert_into_parent(self, left, key, right):
        parent = left.parent
        if parent is None:                         # 루트가 나뉨 → 새 루트 (트리가 위로 자람)
            root = Node(is_leaf=False)
            root.keys = [key]
            root.children = [left, right]
            left.parent = right.parent = root
            self.root = root
            return
        i = parent.children.index(left)            # left 바로 오른쪽에 right를 끼움
        parent.keys.insert(i, key)
        parent.children.insert(i + 1, right)
        right.parent = parent
        if len(parent.keys) > self.max_keys:       # 부모도 넘치면 또 나눔
            self._split_internal(parent)

    # ---- 확인용 -----------------------------------------------------------
    def height(self):
        """루트에서 리프까지 노드 수. 노드 하나뿐이면 1."""
        h, node = 1, self.root
        while not node.is_leaf:
            node = node.children[0]
            h += 1
        return h

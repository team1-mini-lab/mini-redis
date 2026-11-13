class Node:
	def __init__(self, key, value, next = None):
		self.key = key
		self.value = value
		self.next = next
          
class HashTable:
    """해시 테이블 저장소.
바깥은 버킷 리스트, 안쪽 체인은 연결 리스트(Node)로 한다.
"""
    def __init__(self, capacity=4):
        self.capacity = capacity  
        self.buckets = [None] * capacity  
        self.size = 0  

    def set(self, key, value, ttl=None):
        index = self._get_bucket_index(key)
        head = self.buckets[index]
        node = head
        while node is not None:
            if node.key == key:
                node.value = value
                return                   
            node = node.next
        self.buckets[index] = Node(key, value, head)
        self.size += 1
        if self.size / self.capacity > 0.75:                
            self._resize()
            
    def _resize(self):
        old_buckets = self.buckets                    
        self.capacity = self.capacity *2          
        self.buckets = [None] * self.capacity           

        for old_head in old_buckets:            
            current = old_head
            while current is not None:
                next_node = current.next
                index = self._get_bucket_index(current.key)
                new_head = self.buckets[index]
                current.next = new_head
                self.buckets[index] = current   
                current = next_node

    def _get_bucket_index(self, key):
        return hash(key) % self.capacity
    
    def get(self, key):
        index = self._get_bucket_index(key)
        current = self.buckets[index]
        while current is not None:
            if current.key == key:
                return current.value
            current = current.next
        return None

    def delete(self, key):
        index = self._get_bucket_index(key)
        prev = None
        current = self.buckets[index]

        while current is not None:
            if current.key == key:
                if prev is None:
                    self.buckets[index] = current.next
                else:                         
                    prev.next = current.next
                self.size -= 1
                return True
            prev = current
            current = current.next
        return False
    
if __name__ == "__main__":
    s = HashTable(capacity=1)      # 일부러 모든 키를 한 칸에 몰기
    s.set("a", 1)
    s.set("b", 2)
    s.set("c", 3)              # 체인: [c] → [b] → [a]

    # set / get
    s.set("a", 10)
    assert s.get("a") == 10
    assert s.size == 3         # 같은 키를 다시 넣어도 개수는 그대로
    assert s.get("z") is None  # 없는 키

    # delete: 중간 → 끝 → 첫 노드
    assert s.delete("b") is True
    assert s.get("a") == 10 and s.get("c") == 3
    assert s.delete("a") is True
    assert s.delete("c") is True
    assert s.delete("c") is False   # 이미 지운 키
    assert s.size == 0

    print("모든 테스트 통과!")

    s = HashTable()                # capacity 4로 시작
    for i in range(100):
        s.set(f"k{i}", i)
    print(s.capacity, s.size)  # 256 100 이 나오면 정상
    assert all(s.get(f"k{i}") == i for i in range(100))
    print("3단계 통과!")
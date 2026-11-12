"""해시 테이블 단위 테스트 (2단계)."""
import unittest

from mini_redis.hashtable import HashTable, fnv1a


def same_bucket(key):
    """모든 키를 0번 칸으로 보내 일부러 충돌을 만드는 해시 함수."""
    return 0


class HashTableTest(unittest.TestCase):
    def test_put_then_get(self):
        t = HashTable()
        self.assertTrue(t.put("name", "현지"))
        self.assertEqual(t.get("name"), "현지")
        self.assertEqual(len(t), 1)

    def test_put_same_key_overwrites(self):
        t = HashTable()
        t.put("k", 1)
        self.assertFalse(t.put("k", 2))   # 덮어쓰기는 False
        self.assertEqual(t.get("k"), 2)
        self.assertEqual(len(t), 1)       # 개수는 그대로

    def test_missing_key(self):
        t = HashTable()
        self.assertIsNone(t.get("nope"))
        self.assertEqual(t.get("nope", "기본값"), "기본값")
        self.assertFalse(t.remove("nope"))

    def test_collision_chain(self):
        t = HashTable(hash_fn=same_bucket)
        for i in range(100):
            t.put(f"key{i}", i)
        for i in range(100):
            self.assertEqual(t.get(f"key{i}"), i)
        # 체인의 맨 앞(마지막에 넣은 것), 중간, 맨 끝(처음 넣은 것)을 지운다
        for key in ("key99", "key50", "key0"):
            self.assertTrue(t.remove(key))
            self.assertIsNone(t.get(key))
        self.assertEqual(len(t), 97)
        self.assertEqual(t.get("key1"), 1)   # 나머지는 그대로

    def test_debug_dump_shows_chain(self):
        t = HashTable(capacity=4, hash_fn=same_bucket)
        t.put("name", "현지")
        t.put("age", 25)
        self.assertIn("[0] (age → 25) → (name → 현지)", t.debug_dump())

    def test_unicode_keys(self):
        t = HashTable()
        t.put("현지", 1)
        t.put("🙂", 2)
        self.assertEqual((t.get("현지"), t.get("🙂")), (1, 2))

    def test_fnv1a_known_values(self):
        # FNV-1a 64비트 공식 테스트 값
        self.assertEqual(fnv1a(""), 0xCBF29CE484222325)
        self.assertEqual(fnv1a("a"), 0xAF63DC4C8601EC8C)
        self.assertEqual(fnv1a("foobar"), 0x85944171F73967E8)


if __name__ == "__main__":
    unittest.main()

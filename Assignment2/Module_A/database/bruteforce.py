# class BruteForceDB:
#     def __init__(self):
#         self.data = []

#     def insert(self, key):
#         self.data.append(key)

#     def search(self, key):
#         return key in self.data

#     def delete(self, key):
#         if key in self.data:
#             self.data.remove(key)

#     def range_query(self, start, end):
#         return [k for k in self.data if start <= k <= end]

class BruteForceDB:
    def __init__(self):
        self.data = []  # Now list of (key, value) tuples

    def insert(self, key, value=None):
        if value is None:
            value = key  # Fallback if no value provided
        self.data.append((key, value))

    def search(self, key):
        for k, v in self.data:
            if k == key:
                return v
        return None

    def delete(self, key):
        for i, (k, _) in enumerate(self.data):
            if k == key:
                self.data.pop(i)
                return True
        return False

    def range_query(self, start, end):
        return sorted([(k, v) for (k, v) in self.data if start <= k <= end], key=lambda x: x[0])
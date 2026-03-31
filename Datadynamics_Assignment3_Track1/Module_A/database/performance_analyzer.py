"""
Performance Analyzer for B+ Tree vs BruteForceDB Comparison
Benchmarks both data structures across multiple operations and dataset sizes
"""

import time
import random
import tracemalloc
import matplotlib.pyplot as plt
from database.bplustree import BPlusTree

from database.bruteforce import BruteForceDB


class PerformanceAnalyzer:
    """
    Benchmarking framework to compare B+ Tree and BruteForceDB performance
    
    Metrics measured:
    - Insertion time
    - Search time (exact key lookups)
    - Range query time
    - Deletion time
    - Random mixed workload time
    - Peak memory usage
    """
    
    def __init__(self, start=1000, end=20000, step=2000, trials=3):
        """
        Initialize the analyzer with test parameters
        
        Args:
            start: Starting dataset size
            end: Ending dataset size
            step: Step size for dataset growth
            trials: Number of trials per configuration
        """
        self.sizes = list(range(start, end + step, step))
        self.trials = trials
        self.results = {
            'insert': {'bplus': [], 'brute': []},
            'search': {'bplus': [], 'brute': []},
            'range':  {'bplus': [], 'brute': []},
            'delete': {'bplus': [], 'brute': []},
            'random': {'bplus': [], 'brute': []},
            'memory': {'bplus': [], 'brute': []}
        }

    def _insert(self, ds, key, value):
        """Insert into data structure (handles both B+ Tree and BruteForce)"""
        try:
            return ds.insert(key, value)
        except TypeError:
            return ds.insert(key)

    def _random_workload(self, ds, keys, n_ops=1000):
        """Simulate mixed workload with random insert/search/delete operations"""
        ops = ('insert', 'search', 'delete')
        extra_keys = list(range(max(keys) + 1, max(keys) + n_ops + 10))
        ek_idx = 0
        start = time.perf_counter()

        for _ in range(n_ops):
            if not keys:
                break  # Avoid errors if keys empty
            op = random.choice(ops)
            if op == 'insert':
                k = extra_keys[ek_idx]
                ek_idx += 1
                self._insert(ds, k, f"val_{k}")
                keys.append(k)
            elif op == 'search':
                ds.search(random.choice(keys))
            else:  # delete
                k = random.choice(keys)
                ds.delete(k)
                if k in keys:
                    keys.remove(k)

        return time.perf_counter() - start

    def _memory_used(self):
        """Get current and peak memory usage"""
        cur, peak = tracemalloc.get_traced_memory()
        return cur, peak

    def _eval_data_structure(self, ds, keys):
        """Evaluate data structure performance across all operations"""
        out = {}
        
        # Insertion benchmark
        t = 0
        for k in keys:
            start = time.perf_counter()
            self._insert(ds, k, f"val_{k}")
            t += time.perf_counter() - start
        out['insert'] = t

        # Search benchmark (500 random searches)
        search_keys = random.sample(keys, min(500, len(keys)))
        t = 0
        for k in search_keys:
            start = time.perf_counter()
            ds.search(k)
            t += time.perf_counter() - start
        out['search'] = t

        # Range query benchmark (50 queries)
        range_starts = [random.randint(1, max(keys)//2) for _ in range(50)]
        width = max(1, max(keys)//10)
        t = 0
        for rs in range_starts:
            start = time.perf_counter()
            ds.range_query(rs, rs + width)
            t += time.perf_counter() - start
        out['range'] = t

        # Deletion benchmark (500 random deletions)
        delete_keys = random.sample(keys, min(500, len(keys)))
        t = 0
        for k in delete_keys:
            start = time.perf_counter()
            ds.delete(k)
            t += time.perf_counter() - start
        out['delete'] = t

        # Random workload benchmark (1000 mixed operations)
        t = self._random_workload(ds, keys[:], n_ops=1000)
        out['random'] = t

        return out

    def run_benchmarks(self):
        """Run benchmarks for both data structures across all dataset sizes"""
        print("Starting Performance Benchmarking...")
        for size in self.sizes:
            print(f"Testing with {size} records...")
            for ds_name, constructor in [('bplus', lambda: BPlusTree(order=8)),
                                         ('brute', lambda: BruteForceDB())]:
                i_results = {'insert': 0, 'search': 0, 'range': 0, 'delete': 0, 'random': 0}
                i_memory = []
                for _ in range(self.trials):
                    ds = constructor()
                    keys = list(range(1, size+1))
                    random.shuffle(keys)
                    tracemalloc.clear_traces()  # Reset for accurate per-trial memory
                    tracemalloc.start()
                    baseline = self._eval_data_structure(ds, keys.copy())
                    cur, peak = self._memory_used()
                    tracemalloc.stop()
                    i_memory.append(peak)
                    for metric in i_results:
                        i_results[metric] += baseline[metric]
                for metric in ('insert', 'search', 'range', 'delete', 'random'):
                    self.results[metric][ds_name].append(i_results[metric] / self.trials)
                self.results['memory'][ds_name].append(sum(i_memory) / len(i_memory))

    def plot_results(self):
        """Generate performance comparison graphs"""
        fig, axs = plt.subplots(3, 2, figsize=(14, 14))
        fig.suptitle('Performance: B+ Tree vs BruteForceDB', fontsize=16)
        plot_data = [
            ('insert', 'Insertion Time'),
            ('search', 'Search Time (500 queries)'),
            ('range', 'Range Query Time (50 queries)'),
            ('delete', 'Deletion Time (500 queries)'),
            ('random', 'Random Mixed Workload (1000 operations)'),
            ('memory', 'Peak Memory (bytes)')
        ]
        for ax, (metric, title) in zip(axs.flatten(), plot_data):
            ax.plot(self.sizes, self.results[metric]['bplus'], label='B+ Tree', marker='o')
            ax.plot(self.sizes, self.results[metric]['brute'], label='BruteForceDB', marker='x')
            ax.set_title(title)
            ax.set_xlabel('Number of Records')
            ax.set_ylabel('Seconds' if metric != 'memory' else 'Bytes')
            ax.legend()
            ax.grid(True)

        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        plt.show()

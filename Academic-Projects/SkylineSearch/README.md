# Skyline Search Using BBS and Divide-and-Conquer

## Project Overview

This project implements and compares three Skyline Search algorithms using a dataset of points representing homes.

Each point has two dimensions:
- **X:** Total cost of the home
- **Y:** Price per square metre

The objective is to identify skyline points, homes that are not dominated by another home across both dimensions. Lower values are preferred.

## Algorithms Implemented

### 1. Sequential Scan
Examines each point against the other points to identify non-dominated points.

### 2. Branch and Bound Skyline (BBS)
Uses an R-tree and a priority queue to efficiently identify skyline points while pruning dominated entries.

### 3. BBS with Divide-and-Conquer
Splits the dataset into two subspaces based on X, performs BBS on each subset, and merges the local skylines using dominance screening.

## Technologies Used

- Python
- R-tree data structure
- Heap / Priority Queue
- Algorithm Design and Analysis

## Project Files

| File | Description |
|---|---|
| `Skyline_search.py` | Main implementation of the three algorithms |
| `rtree.py` | Supporting R-tree implementation |
| `large_dataset_results.txt` | Results from the 300,000-point dataset |
| `sample_dataset_results.txt` | Sample dataset results and BBS execution trace |

## Results and Comparison

The implementation was evaluated using a dataset containing 300,000 points with a maximum R-tree node capacity of B = 4.

All three methods returned the same seven skyline points.

| Algorithm | Execution Time |
|---|---:|
| Sequential Scan | 1.683407 seconds |
| BBS | 0.000368 seconds |
| BBS with Divide-and-Conquer | 0.000686 seconds |

The results demonstrate the efficiency of BBS compared with the Sequential Scan for this dataset.

## Learning Outcomes

- Implementing and comparing different skyline search algorithms
- Understanding R-tree indexing and spatial data structures
- Applying dominance relationships to multidimensional data
- Analysing algorithm performance using execution time
- Understanding divide-and-conquer techniques

---

**Course:** COMP6210 – Big Data Technologies  
**Project:** Assignment 2 – Individual Task 3: Skyline Search

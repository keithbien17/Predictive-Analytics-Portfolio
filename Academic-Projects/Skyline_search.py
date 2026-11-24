"""
COMP6210 Assignment 2 - Individual Task 3: Skyline Search (BBS)

Methods:
    1. Sequential Scan
    2. Branch and Bound Skyline (BBS) on one R-tree
    3. BBS with Divide-and-Conquer (2 subspaces split by X, then 1d-dominance screening)

All R-trees are built with the shared group module rtree.py.
Each point is a home: x = total cost of the home, y = price per square metre.
Smaller values are preferred in both dimensions.

Run:
    python task3_skyline.py                          -> city1.txt, B from rtree.py
    python task3_skyline.py skyline_search.txt 5     -> sample data, B = 5, with step trace
"""

import sys    # for reading the command line and finding rtree.py
import time   # for timing the searches with perf_counter()
import heapq  # heap (priority queue) for BBS
import math   # for sqrt in the Euclidean mindist

# the shared group module rtree.py sits in the parent folder (Assignment 2/rtree.py)
# get the folder this script is in (swap back-slashes for / so it works on Windows too)
_here = __file__.replace('\\', '/').rsplit('/', 1)[0] if '/' in __file__.replace('\\', '/') else '.'
# add the parent folder so Python can find our shared rtree.py
sys.path.append(_here + '/..')
import rtree


# ---------------------------------------------------------------------------
# Reading data
# ---------------------------------------------------------------------------
def read_points(file_name):
    """Reads the file (each line is id x y) and returns the points as dicts."""
    # all the points from the file go here
    points = []
    # open the file for reading
    with open(file_name, 'r') as f:
        # go through the file line by line
        for line in f:
            # split the line into id, x and y
            parts = line.split()
            # skip lines that are empty or missing values
            if len(parts) < 3:
                continue
            # try to read the line as numbers
            try:
                # turn the values into numbers and save the point
                points.append({'id': int(parts[0]), 'x': float(parts[1]), 'y': float(parts[2])})
            except ValueError:
                continue  # skips a header line such as "ID X Y"
    return points


def build_rtree(points):
    """Builds an R-tree with our shared rtree.py by inserting the points one at a time."""
    # start with an empty tree
    tree = rtree.RTree()
    # insert each point, always starting from the root
    for p in points:
        tree.insert(tree.root, p)
    return tree


# ---------------------------------------------------------------------------
# Dominance
# ---------------------------------------------------------------------------
def dominates(p, q):
    """p dominates q: p is no worse in both dimensions and strictly better in at least one."""
    # p has to be <= q in both x and y, and < in at least one
    return p['x'] <= q['x'] and p['y'] <= q['y'] and (p['x'] < q['x'] or p['y'] < q['y'])


def dominates_mbr(p, mbr):
    """p dominates a whole MBR if it dominates the MBR's lower-left corner (x1, y1)."""
    # same check as dominates(), but against the lower-left corner of the MBR
    return p['x'] <= mbr['x1'] and p['y'] <= mbr['y1'] and (p['x'] < mbr['x1'] or p['y'] < mbr['y1'])


# ---------------------------------------------------------------------------
# Method 1: Sequential Scan
# ---------------------------------------------------------------------------
def sequential_scan(points):
    """
    Check every point against every other point in the dataset.
    A point is a skyline point if no other point dominates it.
    The inner loop stops as soon as one dominating point is found.
    """
    # skyline points we have so far
    skyline = []
    # check every point p
    for p in points:
        # will be True if some point beats p
        dominated = False
        # compare p with all the other points
        for q in points:
            # q dominates p, so p is not in the skyline
            if dominates(q, p):
                dominated = True
                break  # no need to keep checking
        # nothing beat p, so it is a skyline point
        if not dominated:
            skyline.append(p)
    return skyline


# ---------------------------------------------------------------------------
# Method 2: BBS
# ---------------------------------------------------------------------------
def mindist(entry):
    """Euclidean distance from the origin (0, 0):
    sqrt(x^2 + y^2) for a point, sqrt(x1^2 + y1^2) for an MBR (its lower-left corner)."""
    # points are dicts
    if isinstance(entry, dict):
        return math.sqrt(entry['x'] ** 2 + entry['y'] ** 2)
    # for a node, use the lower-left corner of the MBR (the closest point of the MBR to the origin)
    return math.sqrt(entry.MBR['x1'] ** 2 + entry.MBR['y1'] ** 2)


def bbs(tree, trace=None, labels=None):
    """
    Branch and Bound Skyline.
    The heap holds R-tree entries (nodes or points) ordered by mindist.
    - Pop the entry with the smallest mindist.
    - If a skyline point already dominates it, prune it.
    - If it is a point, it is a skyline point.
    - If it is a node, push its children / data points that are not dominated.
    trace and labels are optional and only used to print the steps for the report.
    """
    # skyline points we have so far
    skyline = []
    # heap items are (mindist, counter, entry)
    heap = []
    counter = 0  # tie-breaker so the heap never compares Node objects

    # start with the root of the tree
    root = tree.root
    heapq.heappush(heap, (mindist(root), counter, root))
    counter += 1 # next counter value for the next entry

    # keep going until the heap is empty
    while heap:
        # pop the entry with the smallest mindist (if tied, the one added first comes out)
        d, _, e = heapq.heappop(heap)
        # True if it is a point, False if it is a node
        is_point = isinstance(e, dict)

        # prune if dominated by a skyline point found so far
        pruned_by = None
        # check it against all skyline points we already have
        for s in skyline:
            # points use dominates(), nodes use dominates_mbr()
            if (is_point and dominates(s, e)) or (not is_point and dominates_mbr(s, e.MBR)):
                pruned_by = s
                break  # one is enough, stop checking
        # it is dominated, so skip it
        if pruned_by is not None:
            # only save the step if we are tracing (sample data)
            if trace is not None:
                trace.append('pop %s (mindist=%s) -> pruned, dominated by p%d'
                             % (name_of(e, labels), fmt(d), pruned_by['id']))
            continue

        # a point that is not dominated goes into the skyline
        if is_point:
            skyline.append(e)
            # only save the step if we are tracing
            if trace is not None:
                trace.append('pop %s (mindist=%s) -> added to skyline' % (name_of(e, labels), fmt(d)))
            continue

        # e is a node: expand it
        # leaf -> its points, internal node -> its children
        children = e.data_points if e.is_leaf() else e.child_nodes
        # keep track of what we pushed and skipped (for the trace)
        pushed, skipped = [], []
        # check each child before pushing it
        for c in children:
            # will be True if a skyline point beats this child
            c_dominated = False
            # compare the child with all skyline points so far
            for s in skyline:
                # points use dominates(), nodes use dominates_mbr()
                if (isinstance(c, dict) and dominates(s, c)) or \
                        (not isinstance(c, dict) and dominates_mbr(s, c.MBR)):
                    c_dominated = True
                    break  # one is enough, stop checking
            # dominated children do not go in the heap at all
            if c_dominated:
                skipped.append(c)
                continue
            # push the child with its mindist and the next counter
            heapq.heappush(heap, (mindist(c), counter, c))
            counter += 1 # next counter value for the next entry
            pushed.append(c) # remember it was pushed (for the trace)

        # save what happened and the heap after this step (only when tracing)
        if trace is not None:
            line = 'pop %s (mindist=%s) -> expand, push [%s]' % (
                name_of(e, labels), fmt(d),
                ', '.join('%s:%s' % (name_of(c, labels), fmt(mindist(c))) for c in pushed))
            # add the skipped ones if there were any
            if skipped:
                line += ', skip dominated [%s]' % ', '.join(name_of(c, labels) for c in skipped)
            trace.append(line)
            trace.append('    heap now: [%s]' % ', '.join(
                '%s:%s' % (name_of(h[2], labels), fmt(h[0])) for h in sorted(heap)))

    return skyline


# ---------------------------------------------------------------------------
# Method 3: BBS with Divide-and-Conquer
# ---------------------------------------------------------------------------
def split_by_x(points):
    """Sort by X (then Y) and split into two near-equal halves."""
    # sort by x, and by y if x is the same
    ordered = sorted(points, key=lambda p: (p['x'], p['y']))
    # middle index, the left half gets len // 2 points
    mid = len(ordered) // 2
    return ordered[:mid], ordered[mid:]


def merge_skylines(left_sky, right_sky):
    """
    1d-dominance screening.
    Every left point has x <= every right point, so no right point can dominate a left point:
    the whole left skyline survives.
    A right point is only dominated if a left skyline point is no worse in y, so it is enough
    to compare it with the left skyline point that has the smallest y.
    """
    # nothing on the left, so the right skyline is the answer
    if not left_sky:
        return list(right_sky)
    # left skyline point with the smallest y
    best_left = min(left_sky, key=lambda p: (p['y'], p['x']))
    # every left skyline point stays
    result = list(left_sky)
    # check each right point against best_left only
    for r in right_sky:
        # keep r if best_left does not dominate it
        if not dominates(best_left, r):
            result.append(r)
    return result


def bbs_divide_conquer(tree_left, tree_right):
    """Runs BBS on both half trees, then merges the two local skylines."""
    # skyline of the left half
    left_sky = bbs(tree_left)
    # skyline of the right half
    right_sky = bbs(tree_right)
    # return the final skyline and both local ones (the trace uses them)
    return merge_skylines(left_sky, right_sky), left_sky, right_sky


# ---------------------------------------------------------------------------
# Helpers for output and the Part B trace
# ---------------------------------------------------------------------------
def fmt(v):
    """Prints a number with at most 2 decimals and drops extra zeros (3.50 -> 3.5, 4.00 -> 4)."""
    return ('%.2f' % v).rstrip('0').rstrip('.')


def sort_skyline(sky):
    """Sorts the skyline by x, then y (then id), like the assignment asks."""
    return sorted(sky, key=lambda p: (p['x'], p['y'], p['id']))


def label_nodes(tree):
    """Give every node a readable name (R = root, N1, N2, ... level by level)."""
    # id(node) -> name
    labels = {}
    # nodes on this level, start with the root
    queue = [tree.root]
    labels[id(tree.root)] = 'R'
    # next number for N1, N2, ...
    k = 1
    # go down level by level until no nodes are left
    while queue:
        # nodes for the next level
        nxt = []
        # go through each node on this level
        for node in queue:
            # give each child a name and add it to the next level
            for c in node.child_nodes:
                labels[id(c)] = 'N%d' % k
                k += 1
                nxt.append(c)
        queue = nxt
    return labels


def name_of(e, labels):
    """Gives the name of an entry: pID for a point, or the node label."""
    # points are called p + id
    if isinstance(e, dict):
        return 'p%d' % e['id']
    # no labels, so just call it node
    if labels is None:
        return 'node'
    return labels.get(id(e), 'node')


def describe_tree(tree, labels):
    """Makes text lines that show every node, its MBR and what is inside it."""
    # lines to return
    lines = []

    def walk(node, depth):
        """Writes this node, then its children indented one more level."""
        m = node.MBR
        # MBR as [(x1,y1),(x2,y2)]
        mbr = '[(%s,%s),(%s,%s)]' % (fmt(m['x1']), fmt(m['y1']), fmt(m['x2']), fmt(m['y2']))
        # leaf: list its points
        if node.is_leaf():
            pts = ', '.join('p%d(%s,%s)' % (p['id'], fmt(p['x']), fmt(p['y'])) for p in node.data_points)
            lines.append('    ' * depth + '%s leaf MBR=%s: %s' % (labels[id(node)], mbr, pts))
        # internal node: list its children, then do each child
        else:
            kids = ', '.join(labels[id(c)] for c in node.child_nodes)
            lines.append('    ' * depth + '%s MBR=%s: children %s' % (labels[id(node)], mbr, kids))
            # do each child one level deeper
            for c in node.child_nodes:
                walk(c, depth + 1)

    # start at the root
    walk(tree.root, 0)
    return lines


def skyline_lines(title, sky, run_time):
    """Makes the output for one method: the skyline points, how many, and the running time."""
    # title for this method
    lines = ['=' * 60, title, '=' * 60]
    # one line per skyline point, sorted by x then y
    for p in sort_skyline(sky):
        lines.append('id=%d, x=%.2f, y=%.2f' % (p['id'], p['x'], p['y']))
    lines.append('Number of skyline points: %d' % len(sky))
    lines.append('Running time: %.6f seconds' % run_time)
    lines.append('')
    return lines


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    """Reads the data, builds the trees, times the 3 methods and saves the results."""
    # use the file from the command line, or city1.txt by default
    data_file = sys.argv[1] if len(sys.argv) > 1 else 'city1.txt'
    # second argument (optional) is B
    if len(sys.argv) > 2:
        rtree.B = int(sys.argv[2])  # maximum node capacity, set in the shared module

    # input and output files are read from / saved in the same folder as this script
    script_dir = __file__.replace('\\', '/').rsplit('/', 1)[0] + '/' if '/' in __file__.replace('\\', '/') else ''
    # if only a file name is given, look for it in the script folder
    if '/' not in data_file.replace('\\', '/') and ':' not in data_file:
        data_file = script_dir + data_file

    # file name without the folder and .txt, e.g. city1
    base = data_file.replace('\\', '/').split('/')[-1].rsplit('.', 1)[0]
    # city1 -> task3_output.txt, other files -> task3_output_<name>.txt
    out_file = script_dir + ('task3_output.txt' if base == 'city1' else 'task3_output_%s.txt' % base)

    # read input and build trees (not timed)
    points = read_points(data_file)
    trace_on = len(points) <= 50  # step-by-step trace only for small sample data

    # one tree with all points for BBS
    tree = build_rtree(points)
    # split by x and build one tree per half for divide-and-conquer
    left_pts, right_pts = split_by_x(points)
    tree_left = build_rtree(left_pts)
    tree_right = build_rtree(right_pts)

    # Method 1: Sequential Scan (timed)
    t0 = time.perf_counter()
    sky_seq = sequential_scan(points)
    t_seq = time.perf_counter() - t0  # running time = end time - start time

    # Method 2: BBS (timed)
    t0 = time.perf_counter()
    sky_bbs = bbs(tree)
    t_bbs = time.perf_counter() - t0

    # Method 3: BBS with Divide-and-Conquer (timed)
    t0 = time.perf_counter()
    sky_dc, left_sky, right_sky = bbs_divide_conquer(tree_left, tree_right)
    t_dc = time.perf_counter() - t0

    # output (not timed)
    lines = ['Task 3: Skyline Search',
             'Dataset: %s (%d points), maximum node capacity B = %d' % (base + '.txt', len(points), rtree.B),
             '']
    lines += skyline_lines('Method 1: Sequential Scan', sky_seq, t_seq)
    lines += skyline_lines('Method 2: BBS', sky_bbs, t_bbs)
    lines += skyline_lines('Method 3: BBS with Divide-and-Conquer', sky_dc, t_dc)

    # check that all 3 methods got the same skyline (compare the ids)
    same = (sorted(p['id'] for p in sky_seq) == sorted(p['id'] for p in sky_bbs)
            == sorted(p['id'] for p in sky_dc))
    lines.append('All three methods return the same skyline: %s' % ('Yes' if same else 'NO'))

    # step by step trace for the report (only for the sample data)
    if trace_on:
        lines += ['', '#' * 60, 'Part B trace (for the report)', '#' * 60, '']

        # names for the nodes in the main tree
        labels = label_nodes(tree)
        lines.append('R-tree on all points:')
        lines += describe_tree(tree, labels)
        lines += ['', 'BBS steps:']
        # run BBS again but with tracing on (this run is not timed)
        steps = []
        bbs(tree, steps, labels)
        lines += steps

        # which points went to each half
        lines += ['', 'Divide-and-Conquer split (sorted by X):',
                  '  Left : ' + ', '.join('p%d' % p['id'] for p in left_pts),
                  '  Right: ' + ', '.join('p%d' % p['id'] for p in right_pts), '']
        # print each half tree and trace BBS on it
        for name, t, pts in (('Left', tree_left, left_pts), ('Right', tree_right, right_pts)):
            lb = label_nodes(t)
            lines.append('R-tree on %s half:' % name)
            lines += describe_tree(t, lb)
            lines.append('BBS steps on %s half:' % name)
            steps = []
            bbs(t, steps, lb)
            lines += steps
            lines.append('')
        lines.append('Left local skyline : ' + ', '.join('p%d' % p['id'] for p in sort_skyline(left_sky)))
        lines.append('Right local skyline: ' + ', '.join('p%d' % p['id'] for p in sort_skyline(right_sky)))
        # show the 1d-dominance screening for the merge
        if left_sky:
            # left skyline point with the smallest y
            b = min(left_sky, key=lambda p: (p['y'], p['x']))
            lines.append('Left skyline point with smallest y: p%d (y=%s)' % (b['id'], fmt(b['y'])))
            # check each right skyline point against it
            for r in sort_skyline(right_sky):
                verdict = 'dominated -> removed' if dominates(b, r) else 'kept'
                lines.append('  p%d (y=%s): %s' % (r['id'], fmt(r['y']), verdict))
        lines.append('Final skyline: ' + ', '.join('p%d' % p['id'] for p in sort_skyline(sky_dc)))

    # put all lines together, print them and save to the output file
    text = '\n'.join(lines)
    print(text)
    with open(out_file, 'w') as f:
        f.write(text + '\n')
    print('\nSaved to %s' % out_file)


# only run main() when this file is run directly
if __name__ == '__main__':
    main()

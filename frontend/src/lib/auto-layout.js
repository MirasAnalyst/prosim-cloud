/**
 * Topological-sort based left-to-right auto-layout for AI-generated flowsheets.
 */
const H_SPACING = 250;
const V_SPACING = 150;
const START_X = 100;
const START_Y = 100;
/**
 * Compute left-to-right positions for equipment nodes using
 * longest-path layering (Kahn's algorithm variant).
 */
export function autoLayout(equipmentIds, connections) {
    // Build adjacency and in-degree maps
    const adj = new Map();
    const inDegree = new Map();
    for (const id of equipmentIds) {
        adj.set(id, []);
        inDegree.set(id, 0);
    }
    for (const conn of connections) {
        adj.get(conn.source_id)?.push(conn.target_id);
        inDegree.set(conn.target_id, (inDegree.get(conn.target_id) ?? 0) + 1);
    }
    // Longest-path depth via modified Kahn's algorithm
    const depth = new Map();
    const queue = [];
    for (const id of equipmentIds) {
        if ((inDegree.get(id) ?? 0) === 0) {
            queue.push(id);
            depth.set(id, 0);
        }
    }
    while (queue.length > 0) {
        const node = queue.shift();
        const nodeDepth = depth.get(node) ?? 0;
        for (const neighbor of adj.get(node) ?? []) {
            // Use longest path so branches get spread out
            const newDepth = nodeDepth + 1;
            if (newDepth > (depth.get(neighbor) ?? 0)) {
                depth.set(neighbor, newDepth);
            }
            inDegree.set(neighbor, (inDegree.get(neighbor) ?? 0) - 1);
            if ((inDegree.get(neighbor) ?? 0) === 0) {
                queue.push(neighbor);
            }
        }
    }
    // Handle disconnected nodes (no edges) — assign depth 0 if not yet set
    for (const id of equipmentIds) {
        if (!depth.has(id)) {
            depth.set(id, 0);
        }
    }
    // Group nodes by column (depth)
    const columns = new Map();
    for (const id of equipmentIds) {
        const col = depth.get(id) ?? 0;
        if (!columns.has(col))
            columns.set(col, []);
        columns.get(col).push(id);
    }
    // Assign positions: left-to-right columns, vertically centered
    const maxColumnSize = Math.max(...[...columns.values()].map((ids) => ids.length));
    const maxTotalHeight = (maxColumnSize - 1) * V_SPACING;
    const positions = [];
    for (const [col, ids] of columns) {
        const x = START_X + col * H_SPACING;
        const totalHeight = (ids.length - 1) * V_SPACING;
        const topY = START_Y + (maxTotalHeight - totalHeight) / 2;
        for (let i = 0; i < ids.length; i++) {
            positions.push({
                id: ids[i],
                x,
                y: topY + i * V_SPACING,
            });
        }
    }
    return positions;
}

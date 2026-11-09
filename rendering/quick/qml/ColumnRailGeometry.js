.pragma library

// Pure retained column projection. Called by ordinary geometry bindings when their inputs change and by the
// selected Edit layer once to predict a discrete reorder. No saved state, provider, item or cadence lives here.
function project(order, widths, gaps, geometry, normalizationWidth, laneWidth) {
    const result = {}
    let start = 0.0
    for (let i = 0; i < order.length; ++i) {
        const role = order[i]
        const authoredWidth = Math.max(1.0, Number(widths[role]))
        const record = geometry ? geometry[role] : null
        const scale = record && record.width_scale !== undefined ? Number(record.width_scale) : 1.0
        const offset = record && record.x_offset !== undefined ? Number(record.x_offset) : 0.0
        const x = Math.max(0.0, Math.min(Math.max(0.0, laneWidth - 1.0),
                                        start + offset * normalizationWidth))
        result[role] = {x: x, width: Math.max(1.0, Math.min(laneWidth - x, authoredWidth * scale))}
        start += authoredWidth
        if (i + 1 < order.length) {
            const pair = role + ":" + order[i + 1]
            start += Number(gaps[pair] !== undefined ? gaps[pair] : gaps.defaultGap)
        }
    }
    return result
}

function swapped(order, source, target) {
    const result = order.slice()
    const first = result.indexOf(source), second = result.indexOf(target)
    if (first < 0 || second < 0 || first === second)
        throw new Error("Invalid semantic column swap")
    result[first] = target
    result[second] = source
    return result
}

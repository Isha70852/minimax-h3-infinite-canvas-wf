export const uid = () => crypto.randomUUID();
export const megapixelOptions = Array.from({ length: 19 }, (_, i) => (i + 2) / 10);
export function resolutionLabel(mp, aspect) {
  const [w, h] = aspect.split(' ')[0].split(':').map(Number);
  const scale = Math.sqrt((mp === 1 ? .98 : mp) * 1024 * 1024 / (w * h));
  return `${mp === 1 ? '1.0（0.98）' : mp.toFixed(1)} MP · ${Math.round(w * scale / 32) * 32} × ${Math.round(h * scale / 32) * 32}`;
}
export const modeNames = {
  T2VA: "文生影片",
  FL2VA: "首尾生影片",
  Ref2VA: "參考生影片",
};
export const kindNames = { image: "圖片", video: "影片", audio: "聲音" };
export const activeStatuses = [
  "uploading",
  "submitting",
  "queued",
  "running",
  "downloading",
  "reconnecting",
];
export function duplicateNode(node, edges) {
  const id = uid();
  return {
    node: {
      ...structuredClone(node),
      id,
      position: { x: node.position.x + 70, y: node.position.y + 90 },
      selected: true,
      data: { ...structuredClone(node.data), label: node.data.label + " 副本" },
    },
    edges: edges
      .filter((e) => e.source === node.id || e.target === node.id)
      .map((e) => ({
        ...structuredClone(e),
        id: uid(),
        source: e.source === node.id ? id : e.source,
        target: e.target === node.id ? id : e.target,
      })),
  };
}
export function referenceRows(nodeId, edges, assets) {
  const rows = edges
    .filter((e) => e.target === nodeId)
    .map((e) => ({
      edge: e,
      asset: assets.find((a) => a.id === e.data?.asset_id),
      role: e.data?.role || "reference",
    }))
    .filter((r) => r.asset);
  const roles = { first: 0, last: 1, reference: 2 },
    kinds = { image: 0, video: 1, audio: 2 };
  rows.sort(
    (a, b) =>
      roles[a.role] - roles[b.role] ||
      kinds[a.asset.kind] - kinds[b.asset.kind],
  );
  const counters = { image: 0, video: 0, audio: 0 };
  return rows.map((r) => {
    const n = ++counters[r.asset.kind];
    return {
      ...r,
      alias: kindNames[r.asset.kind] + n,
      tag: `<${{ image: "Picture", video: "Video", audio: "Audio" }[r.asset.kind]} ${n}>`,
    };
  });
}

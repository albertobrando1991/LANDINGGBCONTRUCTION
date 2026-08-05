export function moveVoceIds(voci, fromIndex, delta) {
  const toIndex = fromIndex + delta;
  if (toIndex < 0 || toIndex >= voci.length) {
    return voci.map((voce) => voce.id);
  }
  const ids = voci.map((voce) => voce.id);
  const [moved] = ids.splice(fromIndex, 1);
  ids.splice(toIndex, 0, moved);
  return ids;
}

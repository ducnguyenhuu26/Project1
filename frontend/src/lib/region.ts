export type Region = [number, number, number, number];
export type ImagePoint = { x: number; y: number };

/** Map pointer coordinates through object-fit: contain, including letterbox space. */
export function imagePoint(clientX: number, clientY: number, rect: Pick<DOMRect, 'left' | 'top' | 'width' | 'height'>,
                           imageWidth: number, imageHeight: number, clamp = false): ImagePoint | null {
  if (rect.width <= 0 || rect.height <= 0 || imageWidth <= 0 || imageHeight <= 0) return null;
  const scale = Math.min(rect.width / imageWidth, rect.height / imageHeight);
  const shownWidth = imageWidth * scale;
  const shownHeight = imageHeight * scale;
  const imageLeft = rect.left + (rect.width - shownWidth) / 2;
  const imageTop = rect.top + (rect.height - shownHeight) / 2;
  const x = (clientX - imageLeft) / scale;
  const y = (clientY - imageTop) / scale;
  if (!clamp && (x < 0 || y < 0 || x > imageWidth || y > imageHeight)) return null;
  return { x: Math.min(imageWidth, Math.max(0, x)), y: Math.min(imageHeight, Math.max(0, y)) };
}

export function regionFromPoints(a: ImagePoint, b: ImagePoint): Region {
  return [Math.min(a.x, b.x), Math.min(a.y, b.y), Math.max(a.x, b.x), Math.max(a.y, b.y)];
}

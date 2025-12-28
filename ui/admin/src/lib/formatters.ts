export function toTitleCase(value: string): string {
  const normalized = value.replace(/[_-]+/g, ' ').trim();

  if (!normalized) {
    return '';
  }

  return normalized
    .split(/\s+/)
    .map((word) =>
      word
        .split('/')
        .map((segment) => (segment ? segment[0].toUpperCase() + segment.slice(1).toLowerCase() : ''))
        .join('/')
    )
    .join(' ');
}

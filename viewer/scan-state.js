// Small pure helpers, kept apart from the page so they can be tested with plain node.

export const STATUS_LABELS = {
  uploaded: "Queued",
  validating: "Checking file",
  processing: "Building preview",
  ready: "Ready",
  failed: "Failed",
};

export function isFinal(status) {
  return status === "ready" || status === "failed";
}

export function anyActive(scans) {
  return scans.some((scan) => !isFinal(scan.status));
}

export function statusLabel(status) {
  return STATUS_LABELS[status] ?? status;
}

export function formatBytes(bytes) {
  if (bytes == null) return "-";
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(value < 10 ? 1 : 0)} ${units[unit]}`;
}

export function reductionText(scan) {
  if (scan.reduction_pct == null) return "";
  const pct = scan.reduction_pct;
  return pct >= 0 ? `${pct.toFixed(1)}% smaller` : `${Math.abs(pct).toFixed(1)}% larger`;
}

// What to tell the person about a scan that is not showing a model.
export function statusMessage(scan) {
  switch (scan.status) {
    case "uploaded":
      return "Waiting in the queue.";
    case "validating":
      return "Checking the file.";
    case "processing":
      return "Building the preview. This page updates by itself.";
    case "failed":
      return scan.error_message || "Processing failed.";
    default:
      return "";
  }
}

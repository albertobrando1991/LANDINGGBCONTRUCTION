const DEFAULT_EXPORT_MAX_SIDE = 2000;

export function rilievoExportDimensions(
  width,
  height,
  maxSide = DEFAULT_EXPORT_MAX_SIDE,
) {
  const safeWidth = Math.max(1, Number(width) || 1200);
  const safeHeight = Math.max(1, Number(height) || 800);
  const scale = maxSide / Math.max(safeWidth, safeHeight);
  return {
    width: Math.max(1, Math.round(safeWidth * scale)),
    height: Math.max(1, Math.round(safeHeight * scale)),
  };
}

export function rilievoExportBaseName(filename, rilievoId) {
  const withoutExtension = String(filename || "")
    .replace(/\.[a-z0-9]{2,5}$/i, "")
    .trim();
  const fallback = `rilievo-${String(rilievoId || "tavola").slice(0, 8)}`;
  return (withoutExtension || fallback)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9_-]+/gi, "-")
    .replace(/-+/g, "-")
    .replace(/^-+|-+$/g, "")
    .toLowerCase();
}

function canvasBlob(canvas, type, quality) {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) =>
        blob ? resolve(blob) : reject(new Error("Impossibile creare il file.")),
      type,
      quality,
    );
  });
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.rel = "noopener";
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function downloadRilievoPng(canvas, baseName) {
  const blob = await canvasBlob(canvas, "image/png");
  downloadBlob(blob, `${baseName}-annotata.png`);
}

export async function downloadRilievoPdf(canvas, baseName) {
  const { jsPDF } = await import("jspdf");
  const orientation = canvas.width >= canvas.height ? "landscape" : "portrait";
  const pdf = new jsPDF({
    orientation,
    unit: "px",
    format: [canvas.width, canvas.height],
    hotfixes: ["px_scaling"],
    compress: true,
  });
  const pageWidth = pdf.internal.pageSize.getWidth();
  const pageHeight = pdf.internal.pageSize.getHeight();
  pdf.addImage(
    canvas.toDataURL("image/jpeg", 0.94),
    "JPEG",
    0,
    0,
    pageWidth,
    pageHeight,
    undefined,
    "FAST",
  );
  pdf.save(`${baseName}-annotata.pdf`);
}

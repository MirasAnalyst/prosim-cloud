import { toSvg, toPng } from 'html-to-image';
import { downloadBlob, downloadText } from './download-utils';

function getFlowElement(): HTMLElement | null {
  return document.querySelector('.react-flow') as HTMLElement | null;
}

function filterNode(node: HTMLElement): boolean {
  const cls = node.className;
  if (typeof cls !== 'string') return true;
  if (
    cls.includes('react-flow__minimap') ||
    cls.includes('react-flow__controls') ||
    cls.includes('react-flow__attribution') ||
    cls.includes('react-flow__panel')
  ) {
    return false;
  }
  return true;
}

export async function exportCanvasAsSvg() {
  const el = getFlowElement();
  if (!el) return;
  const dataUrl = await toSvg(el, { filter: filterNode });
  // dataUrl is "data:image/svg+xml;charset=utf-8,..."
  const svgContent = decodeURIComponent(dataUrl.split(',')[1] || '');
  downloadText(svgContent, 'flowsheet.svg', 'image/svg+xml');
}

export async function exportCanvasAsPng() {
  const el = getFlowElement();
  if (!el) return;
  const dataUrl = await toPng(el, { filter: filterNode, pixelRatio: 2 });
  const res = await fetch(dataUrl);
  const blob = await res.blob();
  downloadBlob(blob, 'flowsheet.png');
}

export async function exportCanvasAsPdf() {
  const el = getFlowElement();
  if (!el) return;
  const { default: jsPDF } = await import('jspdf');
  const dataUrl = await toPng(el, { filter: filterNode, pixelRatio: 2 });

  const img = new Image();
  img.src = dataUrl;
  await new Promise<void>((resolve) => {
    img.onload = () => resolve();
  });

  const orientation = img.width > img.height ? 'landscape' : 'portrait';
  const pdf = new jsPDF({ orientation, unit: 'px', format: [img.width, img.height] });
  pdf.addImage(dataUrl, 'PNG', 0, 0, img.width, img.height);
  pdf.save('flowsheet.pdf');
}

import { EquipmentType } from '../../types';

// ViewBox and base sizing data for each equipment shape
const shapeData: Record<EquipmentType, { vw: number; vh: number; baseSize: number }> = {
  [EquipmentType.Mixer]: { vw: 52, vh: 40, baseSize: 78 },
  [EquipmentType.Splitter]: { vw: 52, vh: 40, baseSize: 78 },
  [EquipmentType.Heater]: { vw: 44, vh: 44, baseSize: 66 },
  [EquipmentType.Cooler]: { vw: 44, vh: 44, baseSize: 66 },
  [EquipmentType.HeatExchanger]: { vw: 56, vh: 40, baseSize: 84 },
  [EquipmentType.Separator]: { vw: 36, vh: 60, baseSize: 80 },
  [EquipmentType.Pump]: { vw: 50, vh: 40, baseSize: 75 },
  [EquipmentType.Compressor]: { vw: 44, vh: 44, baseSize: 66 },
  [EquipmentType.Valve]: { vw: 44, vh: 32, baseSize: 66 },
  [EquipmentType.DistillationColumn]: { vw: 36, vh: 76, baseSize: 110 },
  [EquipmentType.CSTRReactor]: { vw: 40, vh: 56, baseSize: 80 },
  [EquipmentType.PFRReactor]: { vw: 60, vh: 32, baseSize: 90 },
  [EquipmentType.ConversionReactor]: { vw: 40, vh: 56, baseSize: 80 },
};

/** Compute pixel dimensions for the canvas node, preserving aspect ratio. */
export function getNodeDimensions(type: EquipmentType): { width: number; height: number } {
  const { vw, vh, baseSize } = shapeData[type];
  if (vw >= vh) {
    return { width: baseSize, height: Math.round(baseSize * vh / vw) };
  }
  return { width: Math.round(baseSize * vw / vh), height: baseSize };
}

/** Compute pixel dimensions for the palette thumbnail. */
export function getPaletteIconDimensions(type: EquipmentType): { width: number; height: number } {
  const { vw, vh } = shapeData[type];
  const base = 22;
  if (vw >= vh) {
    return { width: base, height: Math.round(base * vh / vw) };
  }
  return { width: Math.round(base * vw / vh), height: base };
}

// Color constants (HYSYS/DWSIM gray scheme)
const FILL = '#D4D4D8';
const FILL_SEL = '#DBEAFE';
const STROKE = '#71717A';
const STROKE_SEL = '#3B82F6';
const SW = 1.5;
const DETAIL = '#A1A1AA';
const LABEL_CLR = '#52525B';

interface EquipmentIconProps {
  type: EquipmentType;
  width?: number;
  height?: number;
  selected?: boolean;
}

export function EquipmentIcon({ type, width, height, selected = false }: EquipmentIconProps) {
  const fill = selected ? FILL_SEL : FILL;
  const stroke = selected ? STROKE_SEL : STROKE;
  const { vw, vh } = shapeData[type];
  const dims = getNodeDimensions(type);
  const w = width ?? dims.width;
  const h = height ?? dims.height;

  const svgProps = { width: w, height: h, viewBox: `0 0 ${vw} ${vh}` };

  switch (type) {
    // ── Mixer: pentagon arrow pointing right ──
    case EquipmentType.Mixer:
      return (
        <svg {...svgProps}>
          <polygon
            points="2,2 34,2 50,20 34,38 2,38"
            fill={fill} stroke={stroke} strokeWidth={SW} strokeLinejoin="round"
          />
        </svg>
      );

    // ── Splitter: pentagon arrow pointing left ──
    case EquipmentType.Splitter:
      return (
        <svg {...svgProps}>
          <polygon
            points="2,20 18,2 50,2 50,38 18,38"
            fill={fill} stroke={stroke} strokeWidth={SW} strokeLinejoin="round"
          />
        </svg>
      );

    // ── Heater: diamond with "H" ──
    case EquipmentType.Heater:
      return (
        <svg {...svgProps}>
          <polygon
            points="22,2 42,22 22,42 2,22"
            fill={fill} stroke={stroke} strokeWidth={SW} strokeLinejoin="round"
          />
          <text x="22" y="27" textAnchor="middle" fill={LABEL_CLR}
            fontSize="14" fontWeight="bold" fontFamily="Arial, sans-serif">H</text>
        </svg>
      );

    // ── Cooler: diamond with "C" ──
    case EquipmentType.Cooler:
      return (
        <svg {...svgProps}>
          <polygon
            points="22,2 42,22 22,42 2,22"
            fill={fill} stroke={stroke} strokeWidth={SW} strokeLinejoin="round"
          />
          <text x="22" y="27" textAnchor="middle" fill={LABEL_CLR}
            fontSize="14" fontWeight="bold" fontFamily="Arial, sans-serif">C</text>
        </svg>
      );

    // ── Heat Exchanger: ellipse with diagonal baffle line ──
    case EquipmentType.HeatExchanger:
      return (
        <svg {...svgProps}>
          <ellipse cx="28" cy="20" rx="26" ry="18"
            fill={fill} stroke={stroke} strokeWidth={SW} />
          <line x1="8" y1="34" x2="48" y2="6"
            stroke={DETAIL} strokeWidth={SW} />
        </svg>
      );

    // ── Separator: vertical capsule with liquid level ──
    case EquipmentType.Separator:
      return (
        <svg {...svgProps}>
          <rect x="4" y="4" width="28" height="52" rx="14"
            fill={fill} stroke={stroke} strokeWidth={SW} />
          <line x1="6" y1="38" x2="30" y2="38"
            stroke={DETAIL} strokeWidth={1} strokeDasharray="3,2" />
        </svg>
      );

    // ── Pump: circle body + triangular discharge nozzle ──
    case EquipmentType.Pump:
      return (
        <svg {...svgProps}>
          <circle cx="20" cy="20" r="16"
            fill={fill} stroke={stroke} strokeWidth={SW} />
          <polygon points="34,10 48,20 34,30"
            fill={fill} stroke={stroke} strokeWidth={SW} strokeLinejoin="round" />
        </svg>
      );

    // ── Compressor: trapezoid (wide inlet left, narrow outlet right) ──
    case EquipmentType.Compressor:
      return (
        <svg {...svgProps}>
          <polygon
            points="2,2 42,10 42,34 2,42"
            fill={fill} stroke={stroke} strokeWidth={SW} strokeLinejoin="round"
          />
        </svg>
      );

    // ── Valve: bowtie (two triangles meeting at center) ──
    case EquipmentType.Valve:
      return (
        <svg {...svgProps}>
          <polygon points="2,4 22,16 2,28"
            fill={fill} stroke={stroke} strokeWidth={SW} strokeLinejoin="round" />
          <polygon points="42,4 22,16 42,28"
            fill={fill} stroke={stroke} strokeWidth={SW} strokeLinejoin="round" />
        </svg>
      );

    // ── Distillation Column: tall rounded rect with tray lines ──
    case EquipmentType.DistillationColumn:
      return (
        <svg {...svgProps}>
          <rect x="4" y="4" width="28" height="68" rx="6"
            fill={fill} stroke={stroke} strokeWidth={SW} />
          {[16, 25, 34, 43, 52, 61].map((y) => (
            <line key={y} x1="8" y1={y} x2="28" y2={y}
              stroke={DETAIL} strokeWidth={0.8} />
          ))}
        </svg>
      );

    // ── CSTR Reactor: vertical cylinder with stirrer ──
    case EquipmentType.CSTRReactor:
      return (
        <svg {...svgProps}>
          {/* Body + bottom arc */}
          <path d="M6,12 L6,44 A14,6 0 0,0 34,44 L34,12 Z"
            fill={fill} stroke={stroke} strokeWidth={SW} />
          {/* Top ellipse cap */}
          <ellipse cx="20" cy="12" rx="14" ry="6"
            fill={fill} stroke={stroke} strokeWidth={SW} />
          {/* Stirrer shaft */}
          <line x1="20" y1="6" x2="20" y2="38" stroke={DETAIL} strokeWidth={1.5} />
          {/* Agitator blades */}
          <line x1="13" y1="26" x2="27" y2="26" stroke={DETAIL} strokeWidth={1.5} />
          <line x1="13" y1="34" x2="27" y2="34" stroke={DETAIL} strokeWidth={1.5} />
        </svg>
      );

    // ── PFR Reactor: horizontal capsule with segment lines ──
    case EquipmentType.PFRReactor:
      return (
        <svg {...svgProps}>
          <rect x="4" y="4" width="52" height="24" rx="12"
            fill={fill} stroke={stroke} strokeWidth={SW} />
          {[18, 30, 42].map((x) => (
            <line key={x} x1={x} y1="6" x2={x} y2="26"
              stroke={DETAIL} strokeWidth={0.8} />
          ))}
        </svg>
      );

    // ── Conversion Reactor: vertical cylinder with "C" label ──
    case EquipmentType.ConversionReactor:
      return (
        <svg {...svgProps}>
          <path d="M6,12 L6,44 A14,6 0 0,0 34,44 L34,12 Z"
            fill={fill} stroke={stroke} strokeWidth={SW} />
          <ellipse cx="20" cy="12" rx="14" ry="6"
            fill={fill} stroke={stroke} strokeWidth={SW} />
          <text x="20" y="33" textAnchor="middle" fill={LABEL_CLR}
            fontSize="14" fontWeight="bold" fontFamily="Arial, sans-serif">C</text>
        </svg>
      );

    default:
      return null;
  }
}

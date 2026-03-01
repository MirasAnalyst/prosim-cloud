import { EquipmentType } from '../../types';

// ViewBox and base sizing data for each equipment shape
const shapeData: Record<string, { vw: number; vh: number; baseSize: number }> = {
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
  [EquipmentType.Absorber]: { vw: 36, vh: 76, baseSize: 110 },
  [EquipmentType.Stripper]: { vw: 36, vh: 76, baseSize: 110 },
  [EquipmentType.Cyclone]: { vw: 40, vh: 60, baseSize: 80 },
  [EquipmentType.ThreePhaseSeparator]: { vw: 56, vh: 40, baseSize: 84 },
  [EquipmentType.Crystallizer]: { vw: 44, vh: 56, baseSize: 80 },
  [EquipmentType.Dryer]: { vw: 52, vh: 40, baseSize: 78 },
  [EquipmentType.Filter]: { vw: 40, vh: 50, baseSize: 75 },
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

    // ── Cyclone: conical body with tangential inlet ──
    case EquipmentType.Cyclone:
      return (
        <svg {...svgProps}>
          {/* Cylinder top */}
          <rect x="8" y="4" width="24" height="22" rx="3"
            fill={fill} stroke={stroke} strokeWidth={SW} />
          {/* Cone bottom */}
          <polygon points="8,26 32,26 24,56 16,56"
            fill={fill} stroke={stroke} strokeWidth={SW} strokeLinejoin="round" />
          {/* Vortex finder (top outlet) */}
          <line x1="20" y1="4" x2="20" y2="12" stroke={DETAIL} strokeWidth={1.5} />
          {/* Spiral hint */}
          <path d="M14,14 C14,10 26,10 26,14 C26,18 14,18 14,14"
            fill="none" stroke={DETAIL} strokeWidth={0.8} />
        </svg>
      );

    // ── Absorber: tall column with "A" label + packing lines ──
    case EquipmentType.Absorber:
      return (
        <svg {...svgProps}>
          <rect x="4" y="4" width="28" height="68" rx="6"
            fill={fill} stroke={stroke} strokeWidth={SW} />
          {[20, 30, 40, 50].map((y) => (
            <line key={y} x1="8" y1={y} x2="28" y2={y}
              stroke={DETAIL} strokeWidth={0.8} strokeDasharray="2,2" />
          ))}
          <text x="18" y="16" textAnchor="middle" fill={LABEL_CLR}
            fontSize="10" fontWeight="bold" fontFamily="Arial, sans-serif">A</text>
        </svg>
      );

    // ── Stripper: tall column with "S" label + packing lines ──
    case EquipmentType.Stripper:
      return (
        <svg {...svgProps}>
          <rect x="4" y="4" width="28" height="68" rx="6"
            fill={fill} stroke={stroke} strokeWidth={SW} />
          {[20, 30, 40, 50].map((y) => (
            <line key={y} x1="8" y1={y} x2="28" y2={y}
              stroke={DETAIL} strokeWidth={0.8} strokeDasharray="2,2" />
          ))}
          <text x="18" y="16" textAnchor="middle" fill={LABEL_CLR}
            fontSize="10" fontWeight="bold" fontFamily="Arial, sans-serif">S</text>
        </svg>
      );

    // ── Three-Phase Separator: horizontal drum with 3 sections ──
    case EquipmentType.ThreePhaseSeparator:
      return (
        <svg {...svgProps}>
          <rect x="4" y="8" width="48" height="24" rx="6"
            fill={fill} stroke={stroke} strokeWidth={SW} />
          <line x1="20" y1="8" x2="20" y2="32" stroke={DETAIL} strokeWidth={0.8} strokeDasharray="2,2" />
          <line x1="36" y1="8" x2="36" y2="32" stroke={DETAIL} strokeWidth={0.8} strokeDasharray="2,2" />
          <text x="12" y="23" textAnchor="middle" fill={LABEL_CLR} fontSize="7" fontFamily="Arial">V</text>
          <text x="28" y="23" textAnchor="middle" fill={LABEL_CLR} fontSize="7" fontFamily="Arial">L1</text>
          <text x="44" y="23" textAnchor="middle" fill={LABEL_CLR} fontSize="7" fontFamily="Arial">L2</text>
        </svg>
      );

    // ── Crystallizer: vessel with crystal shapes ──
    case EquipmentType.Crystallizer:
      return (
        <svg {...svgProps}>
          <rect x="6" y="6" width="32" height="40" rx="4"
            fill={fill} stroke={stroke} strokeWidth={SW} />
          <polygon points="18,20 22,14 26,20 22,26" fill="none" stroke={DETAIL} strokeWidth={1} />
          <polygon points="14,32 18,26 22,32 18,38" fill="none" stroke={DETAIL} strokeWidth={0.8} />
          <text x="22" y="48" textAnchor="middle" fill={LABEL_CLR} fontSize="7" fontFamily="Arial">CR</text>
        </svg>
      );

    // ── Dryer: rectangular box with wavy lines ──
    case EquipmentType.Dryer:
      return (
        <svg {...svgProps}>
          <rect x="6" y="6" width="40" height="28" rx="3"
            fill={fill} stroke={stroke} strokeWidth={SW} />
          <path d="M12,16 Q16,12 20,16 Q24,20 28,16 Q32,12 36,16" fill="none" stroke={DETAIL} strokeWidth={1} />
          <path d="M12,24 Q16,20 20,24 Q24,28 28,24 Q32,20 36,24" fill="none" stroke={DETAIL} strokeWidth={1} />
        </svg>
      );

    // ── Filter: funnel shape ──
    case EquipmentType.Filter:
      return (
        <svg {...svgProps}>
          <polygon points="4,6 36,6 28,30 12,30"
            fill={fill} stroke={stroke} strokeWidth={SW} strokeLinejoin="round" />
          <rect x="14" y="30" width="12" height="14" rx="2"
            fill={fill} stroke={stroke} strokeWidth={SW} />
          <line x1="10" y1="14" x2="30" y2="14" stroke={DETAIL} strokeWidth={0.8} />
          <line x1="12" y1="20" x2="28" y2="20" stroke={DETAIL} strokeWidth={0.8} />
        </svg>
      );

    default:
      return null;
  }
}

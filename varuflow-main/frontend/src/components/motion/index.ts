// File: src/components/motion/index.ts
// Purpose: Barrel for the shared motion primitives. Import from here:
//   import { Reveal, Stagger, StaggerItem } from "@/components/motion";

export { Reveal } from "./Reveal";
export { Stagger, StaggerItem } from "./Stagger";
export {
  DUR,
  EASE_STANDARD,
  EASE_EMPHASIZED,
  fadeInUp,
  staggerContainer,
} from "./variants";

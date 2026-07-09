import { wholesale } from "./wholesale";
import { retail } from "./retail";
import { restaurants } from "./restaurants";
import type { Solution } from "./types";

export type { Solution };
export const SOLUTIONS: Solution[] = [wholesale, retail, restaurants];

import { inventory } from "./inventory";
import { invoicing } from "./invoicing";
import { finance } from "./finance";
import { pos } from "./pos";
import { ai } from "./ai";
import { analytics } from "./analytics";
import type { Module } from "./types";

export type { Module };
export const MODULES: Module[] = [inventory, invoicing, finance, pos, ai, analytics];

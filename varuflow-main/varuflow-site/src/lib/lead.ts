import { z } from "zod";

export const COMPANY_SIZES = ["1-5", "6-20", "21-50", "51-200", "200+"] as const;

export const leadSchema = z.object({
  name: z.string().trim().min(1).max(200),
  company: z.string().trim().min(1).max(200),
  email: z.email().max(320),
  size: z.enum(COMPANY_SIZES),
  message: z.string().trim().max(2000).optional().or(z.literal("")),
});

export type Lead = z.infer<typeof leadSchema>;

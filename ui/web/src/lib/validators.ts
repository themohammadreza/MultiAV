import { z } from 'zod';

export const uploadFormSchema = z.object({
  file: z
    .instanceof(File)
    .refine((file) => file.size > 0, { message: 'File cannot be empty' })
});

export type UploadFormValues = z.infer<typeof uploadFormSchema>;

const uuidRegex = /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$/;

export function validateJobId(input: string): string {
  const value = input.trim();
  if (!uuidRegex.test(value)) {
    throw new Error('Job ID must be a valid UUID');
  }
  return value;
}
